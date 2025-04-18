import cv2
import pytesseract
from PIL import Image
import re
import os
import time
import json
import numpy as np
from datetime import datetime
from database import CodeSnippet, session
import easyocr  # Import EasyOCR

# Set this if using Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'], gpu=False)  # Set `gpu=True` if you have a GPU and want to use it

def get_timestamp(frame_num, fps):
    seconds = int(frame_num / fps)
    return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"

def preprocess_frame(frame):
    """Apply advanced preprocessing to optimize frame for code OCR."""
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Crop the center region of the frame (where code is likely to appear)
    height, width = gray.shape
    margin_x = int(width * 0.1)  # 10% margin from sides
    margin_y = int(height * 0.1)  # 10% margin from top/bottom
    cropped = gray[margin_y:height-margin_y, margin_x:width-margin_x]
    
    # Scale up the cropped region for better OCR
    scale_factor = 2.0
    scaled = cv2.resize(cropped, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    
    # Apply sharpening filter
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(scaled, -1, kernel)
    
    # Enhance contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(sharpened)
    
    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    
    return binary

def detect_language(code):
    """Advanced language detection for code snippets."""
    python_indicators = [
        r"def\s+\w+\s*\(", r"class\s+\w+", r"import\s+\w+", r"from\s+\w+\s+import",
        r":\s*$", r"^\s+", r"print\(", r"if\s+\w+\s*:", r"for\s+\w+\s+in\s+",
        r"while\s+\w+\s*:", r"try\s*:", r"except\s+", r"with\s+\w+\s+as\s+",
        r"lambda\s+\w+\s*:", r"@\w+", r"__\w+__", r"self\.", r"True", r"False", r"None"
    ]
    javascript_indicators = [
        r"function\s+\w+\s*\(", r"var\s+\w+\s*=", r"let\s+\w+\s*=", r"const\s+\w+\s*=",
        r"document\.", r"window\.", r"console\.log", r"=>\s*{", r"new\s+\w+\(",
        r"prototype\.", r"this\.", r"{\s*\w+\s*:\s*", r"\$\(", r"addEventListener",
        r"function\s*\(", r"typeof\s+", r"undefined", r"null", r"true", r"false"
    ]
    cpp_indicators = [
        r"#include", r"std::", r"int\s+\w+\s*\(", r"void\s+\w+\s*\(", r"cout\s*<<",
        r"cin\s*>>", r"namespace", r"template\s*<", r"class\s+\w+\s*{",
        r"public:", r"private:", r"protected:", r"struct\s+\w+\s*{", r"enum\s+\w+\s*{",
        r"const\s+\w+\s*&", r"::\w+", r"delete\s+", r"new\s+\w+\s*\("
    ]
    java_indicators = [
        r"public\s+(static\s+)?(final\s+)?\w+\s+\w+", r"private\s+\w+\s+\w+",
        r"protected\s+\w+\s+\w+", r"class\s+\w+(\s+extends\s+\w+)?(\s+implements\s+\w+)?",
        r"import\s+java\.", r"System\.out\.print", r"@Override", r"interface\s+\w+",
        r"throws\s+\w+", r"try\s*{", r"catch\s*\(\w+\s+\w+\)\s*{"
    ]
    html_indicators = [
        r"<!DOCTYPE\s+html>", r"<html>", r"</html>", r"<head>", r"</head>",
        r"<body>", r"</body>", r"<div", r"<span", r"<p>", r"<a\s+href", 
        r"<img\s+src", r"<script", r"<style", r"<table", r"<form", r"<input"
    ]
    css_indicators = [
        r"^\s*\.\w+\s*{", r"^\s*#\w+\s*{", r"^\s*\w+\s*{.*}", r"margin(\s*:|-).*?;",
        r"padding(\s*:|-).*?;", r"color\s*:", r"background\s*:", r"font-", r"@media\s+",
        r"display\s*:", r"position\s*:", r"width\s*:", r"height\s*:", r"border\s*:",
        r"\s+!important"
    ]
    sql_indicators = [
        r"SELECT\s+\w+", r"FROM\s+\w+", r"WHERE\s+\w+", r"INSERT\s+INTO",
        r"UPDATE\s+\w+\s+SET", r"DELETE\s+FROM", r"JOIN\s+\w+\s+ON", r"GROUP\s+BY",
        r"ORDER\s+BY", r"HAVING", r"CREATE\s+TABLE", r"ALTER\s+TABLE", r"DROP\s+TABLE"
    ]
    
    language_scores = {
        "Python": sum(1 for pattern in python_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "JavaScript": sum(1 for pattern in javascript_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "C++": sum(1 for pattern in cpp_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "Java": sum(1 for pattern in java_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "HTML": sum(1 for pattern in html_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "CSS": sum(1 for pattern in css_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)),
        "SQL": sum(1 for pattern in sql_indicators if re.search(pattern, code, re.IGNORECASE | re.MULTILINE))
    }
    
    pattern_counts = {
        "Python": len(python_indicators),
        "JavaScript": len(javascript_indicators),
        "C++": len(cpp_indicators),
        "Java": len(java_indicators),
        "HTML": len(html_indicators),
        "CSS": len(css_indicators),
        "SQL": len(sql_indicators)
    }
    
    for lang in language_scores:
        if pattern_counts[lang] > 0:
            language_scores[lang] = language_scores[lang] / pattern_counts[lang]
    
    max_score = max(language_scores.values()) if language_scores else 0
    if max_score > 0.1:
        for lang, score in language_scores.items():
            if score == max_score:
                return lang
    
    return "Unknown"

def format_python_code(code):
    """Reformat Python code to ensure proper indentation."""
    lines = code.splitlines()
    formatted_lines = []
    indent_level = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:  # Skip empty lines
            formatted_lines.append("")
            continue

        # Adjust indentation based on Python block keywords
        if stripped.endswith(":"):
            formatted_lines.append("    " * indent_level + stripped)
            indent_level += 1
        elif stripped.startswith(("elif ", "else:", "except ", "finally:")):
            indent_level = max(indent_level - 1, 0)
            formatted_lines.append("    " * indent_level + stripped)
            indent_level += 1
        elif stripped.startswith(("return", "pass", "break", "continue")):
            formatted_lines.append("    " * indent_level + stripped)
        elif stripped.startswith(("}", ")")):  # Handle closing brackets
            indent_level = max(indent_level - 1, 0)
            formatted_lines.append("    " * indent_level + stripped)
        else:
            formatted_lines.append("    " * indent_level + stripped)

    return "\n".join(formatted_lines)

def format_javascript_code(code):
    """Reformat JavaScript code to ensure proper indentation."""
    lines = code.splitlines()
    formatted_lines = []
    indent_level = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:  # Skip empty lines
            formatted_lines.append("")
            continue

        # Adjust indentation based on brackets
        if stripped.endswith("{"):
            formatted_lines.append("    " * indent_level + stripped)
            indent_level += 1
        elif stripped.startswith("}"):
            indent_level = max(indent_level - 1, 0)
            formatted_lines.append("    " * indent_level + stripped)
        else:
            formatted_lines.append("    " * indent_level + stripped)

    return "\n".join(formatted_lines)

def format_html_code(code):
    """Reformat HTML code with proper indentation."""
    lines = code.splitlines()
    formatted_lines = []
    indent_level = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:  # Skip empty lines
            formatted_lines.append("")
            continue

        # Adjust indentation based on opening and closing tags
        if stripped.startswith("</"):
            indent_level = max(indent_level - 1, 0)
        formatted_lines.append("    " * indent_level + stripped)
        if stripped.endswith(">") and not stripped.startswith("</") and not stripped.endswith("/>"):
            indent_level += 1

    return "\n".join(formatted_lines)

def format_css_code(code):
    """Reformat CSS code with proper indentation."""
    lines = code.splitlines()
    formatted_lines = []
    in_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:  # Skip empty lines
            formatted_lines.append("")
            continue

        if "{" in stripped and "}" not in stripped:
            # Start of CSS block
            formatted_lines.append(stripped)
            in_block = True
        elif "}" in stripped and "{" not in stripped:
            # End of CSS block
            if in_block:
                formatted_lines.append("    " + stripped)
            else:
                formatted_lines.append(stripped)
            in_block = False
        elif in_block:
            # Inside CSS block
            formatted_lines.append("    " + stripped)
        else:
            # Outside any block
            formatted_lines.append(stripped)

    return "\n".join(formatted_lines)

def format_sql_code(code):
    """Reformat SQL code with proper indentation and capitalization."""
    keywords = [
        "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", 
        "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "OUTER JOIN",
        "ON", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS NULL", 
        "IS NOT NULL", "AS", "INSERT INTO", "VALUES", "UPDATE", "SET",
        "DELETE FROM", "CREATE TABLE", "ALTER TABLE", "DROP TABLE"
    ]
    lines = code.splitlines()
    formatted_lines = []

    for line in lines:
        formatted_line = line.strip()
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            formatted_line = re.sub(pattern, keyword, formatted_line, flags=re.IGNORECASE)
        formatted_lines.append(formatted_line)

    return "\n".join(formatted_lines)

def format_generic_code(code):
    """Basic formatting for generic code."""
    lines = code.splitlines()
    formatted_lines = []

    for line in lines:
        formatted_lines.append(line.strip())

    return "\n".join(formatted_lines)

def format_code(code, language):
    """Format code based on detected language."""
    if language == "Python":
        code = cleanup_extracted_text(code)
        return format_python_code(code)
    elif language == "JavaScript":
        return format_javascript_code(code)
    elif language == "HTML":
        return format_html_code(code)
    elif language == "CSS":
        return format_css_code(code)
    elif language == "SQL":
        return format_sql_code(code)
    return format_generic_code(code)

def cleanup_extracted_text(text):
    """Advanced cleanup of OCR errors in code extraction."""
    replacements = {
        "О": "O", "о": "o", "І": "I", "і": "i", "—": "-", "–": "-",
        "''": "\"", "``": "\"", "ˋ": "`", "Revense": "reverse", "modells": "models",
        "tinezens": "timezone", "CHES": "class", "Foraignikay": "ForeignKey",
        "CharRicila": "CharField", "TaxtRicla": "TextField", "DatelinePicld": "DateTimeField",
        "BriodoltsmDatelrine": "DateField", "pubblliisin": "publish"
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    lines = text.splitlines()
    for i in range(len(lines)):
        if lines[i].startswith("    "):
            lines[i] = lines[i].replace("\t", "    ")
    
    return "\n".join(lines)

def is_code_snippet(text):
    """Determine if the extracted text is likely code rather than natural language."""
    if len(text) < 20:
        return False
        
    lines = text.splitlines()
    if len(lines) < 2:
        return False
        
    code_indicators = [
        r"def\s+\w+\s*\(", r"class\s+\w+", r"function\s+\w+",
        r"import\s+\w+", r"from\s+\w+\s+import", r"var\s+\w+\s*=",
        r"let\s+\w+\s*=", r"const\s+\w+\s*=", r"if\s*\(", r"for\s*\(",
        r"while\s*\(", r"{\s*\n", r"}\s*\n", r"<\w+>.*</\w+>",
        r"#include", r"public\s+class", r"private\s+\w+\s+\w+\(",
        r"@Override", r"int\s+\w+\s*\(", r"void\s+\w+\s*\(",
        r"print\(", r"return\s", r"==", r"!=", r"->", r"=>",
        r"//", r"#", r"/\*", r"\*/", r"'''", r'"""'
    ]
    
    indentation_pattern = r"^\s{2,}.*$"
    indented_lines = sum(1 for line in lines if re.match(indentation_pattern, line))
    
    code_symbols = ["{", "}", "[", "]", "(", ")", ";", "=", "==", "!=", ">=", "<=", "+=", "-=", "*=", "/="]
    symbol_count = sum(text.count(symbol) for symbol in code_symbols)
    
    avg_line_length = sum(len(line) for line in lines) / len(lines) if lines else 0
    
    if indented_lines >= 2 or symbol_count > 5:
        return True
    
    for pattern in code_indicators:
        if re.search(pattern, text):
            return True
            
    if 10 <= avg_line_length <= 80:
        return True
    
    return False

def extract_code_from_video(video_path, progress_callback=None):
    """Extract code snippets from the video and save them to the database."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file.")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_num = 0
    recent_codes = []
    sampling_rate = max(1, int(fps * 2))  # Process 1 frame every 2 seconds
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % sampling_rate == 0:
            if progress_callback:
                progress = int((frame_num / total_frames) * 100)
                progress_callback(progress)

            processed = preprocess_frame(frame)

            try:
                # Use EasyOCR for text extraction
                extracted_text = reader.readtext(processed, detail=0)  # Extract text without bounding box details
                extracted_text = "\n".join(extracted_text).strip()  # Combine lines into a single string
                
                if extracted_text:
                    cleaned_text = cleanup_extracted_text(extracted_text)
                    if cleaned_text and is_code_snippet(cleaned_text):
                        language = detect_language(cleaned_text)
                        if language != "Unknown":
                            formatted_code = format_code(cleaned_text, language)
                            timestamp = get_timestamp(frame_num, fps)
                            snippet = CodeSnippet(
                                timestamp=timestamp,
                                language=language,
                                code=formatted_code,
                                source_file=os.path.basename(video_path)
                            )
                            session.add(snippet)
                            session.commit()
                            recent_codes.append(cleaned_text)
                            if len(recent_codes) > 5:
                                recent_codes.pop(0)
                            print(f"Extracted {language} code at {timestamp}")
            except Exception as e:
                print(f"Error processing frame {frame_num}: {str(e)}")

        frame_num += 1

    cap.release()
    if progress_callback:
        progress_callback(100)

def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings using difflib."""
    import difflib
    
    if len(str1) > 1000 or len(str2) > 1000:
        str1_sample = str1[:500] + str1[-500:] if len(str1) > 1000 else str1
        str2_sample = str2[:500] + str2[-500:] if len(str2) > 1000 else str2
        return similarity_ratio(str1_sample, str2_sample)
    
    matcher = difflib.SequenceMatcher(None, str1, str2)
    return matcher.ratio()

def is_duplicate_code(new_code, existing_code, threshold=0.85):
    """Check if the new code is a duplicate of existing code."""
    len_ratio = min(len(new_code), len(existing_code)) / max(len(new_code), len(existing_code))
    if len_ratio < 0.5:
        return False
        
    new_normalized = ' '.join(new_code.split())
    existing_normalized = ' '.join(existing_code.split())
    
    similarity = similarity_ratio(new_normalized, existing_normalized)
    return similarity > threshold

def save_snippets_to_file(snippets, output_path):
    """Save extracted snippets to a JSON file."""
    with open(output_path, 'w') as f:
        json.dump(snippets, f, indent=4)

def load_snippets_from_file(input_path):
    """Load snippets from a JSON file."""
    with open(input_path, 'r') as f:
        return json.load(f)