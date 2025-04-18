import sys
import os
import json  # Add this import
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget,
                            QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                            QFileDialog, QProgressBar, QSplitter, QTreeWidget,
                            QTreeWidgetItem, QTextEdit, QComboBox, QCheckBox,
                            QMessageBox, QDialog, QLineEdit, QDialogButtonBox,
                            QStatusBar, QMenu, QToolBar, QFrame, QGridLayout)
from PyQt6.QtGui import QAction, QFont, QIcon, QColor, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRegularExpression

# Import the database model
from database import CodeSnippet, session, Base, engine
from ocr_extractor import extract_code_from_video

class SyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for code snippets"""
    def __init__(self, parent=None, language="python"):
        super().__init__(parent)
        self.language = language
        self.highlighting_rules = []
        
        self.setup_highlighting_rules()
        
    def setup_highlighting_rules(self):
        # Clear existing rules
        self.highlighting_rules = []
        
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        
        # Python specific
        if self.language.lower() == "python":
            keywords = [
                "and", "as", "assert", "break", "class", "continue", "def",
                "del", "elif", "else", "except", "False", "finally", "for",
                "from", "global", "if", "import", "in", "is", "lambda", "None",
                "nonlocal", "not", "or", "pass", "raise", "return", "True",
                "try", "while", "with", "yield"
            ]
            
            # Add keyword rules
            for word in keywords:
                pattern = QRegularExpression(f"\\b{word}\\b")
                self.highlighting_rules.append((pattern, keyword_format))
            
            # String patterns
            self.highlighting_rules.append((QRegularExpression("\".*\""), string_format))
            self.highlighting_rules.append((QRegularExpression("\'.*\'"), string_format))
            
            # Comments
            self.highlighting_rules.append((QRegularExpression("#[^\n]*"), comment_format))
            
            # Function definitions
            self.highlighting_rules.append((QRegularExpression("\\bdef\\s+\\w+\\s*\\("), function_format))
            
        # JavaScript specific
        elif self.language.lower() == "javascript":
            keywords = [
                "break", "case", "catch", "class", "const", "continue", "debugger",
                "default", "delete", "do", "else", "export", "extends", "false",
                "finally", "for", "function", "if", "import", "in", "instanceof",
                "new", "null", "return", "super", "switch", "this", "throw", "true",
                "try", "typeof", "var", "void", "while", "with", "yield", "let"
            ]
            
            # Add keyword rules
            for word in keywords:
                pattern = QRegularExpression(f"\\b{word}\\b")
                self.highlighting_rules.append((pattern, keyword_format))
            
            # String patterns
            self.highlighting_rules.append((QRegularExpression("\".*\""), string_format))
            self.highlighting_rules.append((QRegularExpression("\'.*\'"), string_format))
            
            # Comments
            self.highlighting_rules.append((QRegularExpression("//[^\n]*"), comment_format))
            
            # Function definitions
            self.highlighting_rules.append((QRegularExpression("\\bfunction\\s+\\w+\\s*\\("), function_format))
        
        # Add more languages as needed...
    
    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class CodeEditor(QTextEdit):
    """Custom text editor with syntax highlighting for code snippets"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        self.highlighter = None
        self.setAcceptRichText(False)
        
    def set_language(self, language):
        self.highlighter = SyntaxHighlighter(self.document(), language)

class ExtractorThread(QThread):
    """Thread for running code extraction in the background"""
    progress_signal = pyqtSignal(int)
    completed_signal = pyqtSignal()

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path

    def run(self):
        try:
            extract_code_from_video(self.video_path, progress_callback=self.progress_signal.emit)
            self.completed_signal.emit()
        except Exception as e:
            print(f"Error: {e}")

class SnippetFilterDialog(QDialog):
    """Dialog for filtering code snippets"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Code Snippets")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Language filter
        self.language_combo = QComboBox()
        self.language_combo.addItem("All Languages")
        self.language_combo.addItems(["Python", "JavaScript", "Java", "C++", "HTML", "CSS"])
        layout.addWidget(QLabel("Language:"))
        layout.addWidget(self.language_combo)
        
        # Time range filter
        time_layout = QHBoxLayout()
        self.start_time = QLineEdit("00:00:00")
        self.end_time = QLineEdit("23:59:59")
        time_layout.addWidget(QLabel("From:"))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("To:"))
        time_layout.addWidget(self.end_time)
        layout.addLayout(time_layout)
        
        # Content search
        self.content_search = QLineEdit()
        layout.addWidget(QLabel("Content contains:"))
        layout.addWidget(self.content_search)
        
        # Remove duplicates option
        self.remove_duplicates = QCheckBox("Remove duplicate snippets")
        self.remove_duplicates.setChecked(True)
        layout.addWidget(self.remove_duplicates)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                       QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_filter_options(self):
        return {
            "language": self.language_combo.currentText() if self.language_combo.currentText() != "All Languages" else None,
            "start_time": self.start_time.text(),
            "end_time": self.end_time.text(),
            "content": self.content_search.text() if self.content_search.text() else None,
            "remove_duplicates": self.remove_duplicates.isChecked()
        }

class ExportDialog(QDialog):
    """Dialog for exporting code snippets"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Code Snippets")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Export format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Python Files (.py)", "HTML (.html)", "Markdown (.md)", "Text Files (.txt)", "JSON (.json)", "PDF (.pdf)"])
        layout.addWidget(QLabel("Export Format:"))
        layout.addWidget(self.format_combo)
        
        # Export options
        self.include_timestamps = QCheckBox("Include timestamps")
        self.include_timestamps.setChecked(True)
        layout.addWidget(self.include_timestamps)
        
        self.include_language = QCheckBox("Include language information")
        self.include_language.setChecked(True)
        layout.addWidget(self.include_language)
        
        self.separate_files = QCheckBox("Export snippets as separate files")
        layout.addWidget(self.separate_files)
        
        # Button to select directory
        dir_layout = QHBoxLayout()
        self.export_path = QLineEdit()
        self.export_path.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.export_path)
        dir_layout.addWidget(self.browse_button)
        
        layout.addWidget(QLabel("Export Directory:"))
        layout.addLayout(dir_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                       QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if directory:
            self.export_path.setText(directory)
    
    def get_export_options(self):
        return {
            "format": self.format_combo.currentText(),
            "include_timestamps": self.include_timestamps.isChecked(),
            "include_language": self.include_language.isChecked(),
            "separate_files": self.separate_files.isChecked(),
            "export_path": self.export_path.text()
        }

class VideoCodeExtractorApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional Code Extractor")
        self.setMinimumSize(1200, 800)
        self.setup_ui()
        self.current_snippets = []
        self.current_file = None
        self.export_service = None
        
        # Initialize database
        Base.metadata.create_all(engine)
    
    def setup_ui(self):
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create top controls
        top_controls = QHBoxLayout()
        
        # Process Video Button
        self.process_button = QPushButton("Process Video")
        self.process_button.setIcon(QIcon.fromTheme("document-open"))
        self.process_button.setMinimumHeight(40)
        self.process_button.clicked.connect(self.process_video)
        top_controls.addWidget(self.process_button)
        
        # Filter Button
        self.filter_button = QPushButton("Filter Snippets")
        self.filter_button.setIcon(QIcon.fromTheme("edit-find"))
        self.filter_button.setMinimumHeight(40)
        self.filter_button.clicked.connect(self.open_filter_dialog)
        top_controls.addWidget(self.filter_button)
        
        # Export Button
        self.export_button = QPushButton("Export Results")
        self.export_button.setIcon(QIcon.fromTheme("document-save"))
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self.open_export_dialog)
        top_controls.addWidget(self.export_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        
        main_layout.addLayout(top_controls)
        main_layout.addWidget(self.progress_bar)
        
        # Create splitter for tree view and code view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Tree widget for code snippets
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Time", "Language", "Size"])
        self.tree_widget.setMinimumWidth(300)
        self.tree_widget.itemClicked.connect(self.show_snippet)
        splitter.addWidget(self.tree_widget)
        
        # Code content area (tabbed)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Add a welcome tab
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_label = QLabel("Welcome to Professional Code Extractor")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 20px;")
        instructions = QLabel("""
        <html>
        <p>This application extracts code snippets from video tutorials and lectures.</p>
        <p>To get started:</p>
        <ol>
            <li>Click <b>Process Video</b> to select and analyze a video file</li>
            <li>View extracted code snippets in the panel on the left</li>
            <li>Click on any snippet to view its code</li>
            <li>Use the <b>Filter</b> button to find specific snippets</li>
            <li>Export your snippets in various formats using the <b>Export</b> button</li>
        </ol>
        </html>
        """)
        instructions.setWordWrap(True)
        welcome_layout.addWidget(welcome_label)
        welcome_layout.addWidget(instructions)
        welcome_layout.addStretch()
        self.tab_widget.addTab(welcome_widget, "Welcome")
        
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
    
    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Open action
        open_action = QAction(QIcon.fromTheme("document-open"), "Open Video", self)
        open_action.triggered.connect(self.process_video)
        toolbar.addAction(open_action)
        
        # View database action
        db_action = QAction(QIcon.fromTheme("folder-open"), "View Database", self)
        db_action.triggered.connect(self.view_database)
        toolbar.addAction(db_action)
        
        toolbar.addSeparator()
        
        # Filter action
        filter_action = QAction(QIcon.fromTheme("edit-find"), "Filter", self)
        filter_action.triggered.connect(self.open_filter_dialog)
        toolbar.addAction(filter_action)
        
        # Export action
        export_action = QAction(QIcon.fromTheme("document-save"), "Export", self)
        export_action.triggered.connect(self.open_export_dialog)
        toolbar.addAction(export_action)
        
        toolbar.addSeparator()
        
        # About action
        about_action = QAction(QIcon.fromTheme("help-about"), "About", self)
        about_action.triggered.connect(self.show_about)
        toolbar.addAction(about_action)
    
    def process_video(self):
        """Select and process a video file"""
        video_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        
        if not video_path:
            return
        
        self.current_file = os.path.basename(video_path)
        self.status_bar.showMessage(f"Processing video: {self.current_file}")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # Clear previous results
        self.tree_widget.clear()
        
        # Start processing thread
        self.extract_thread = ExtractorThread(video_path)
        self.extract_thread.progress_signal.connect(self.update_progress)
        self.extract_thread.completed_signal.connect(self.processing_finished)
        self.extract_thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def display_results(self):
        """Fetch and display extracted snippets from the database."""
        try:
            snippets = session.query(CodeSnippet).all()  # Fetch all snippets from the database
            self.current_snippets = [
                {"timestamp": snippet.timestamp, "language": snippet.language, "code": snippet.code}
                for snippet in snippets
            ]
            self.update_tree_view(self.current_snippets)  # Update the tree view with the snippets

            if not self.current_snippets:
                self.status_bar.showMessage("No code snippets were found in the video.")
            else:
                self.status_bar.showMessage(f"Found {len(self.current_snippets)} code snippets.")
        except Exception as e:
            print(f"Error displaying results: {str(e)}")
            self.status_bar.showMessage(f"Error displaying results: {str(e)}")
    
    def update_tree_view(self, snippets):
        """Update the tree widget with snippet data."""
        self.tree_widget.clear()
        for snippet in snippets:
            snippet_item = QTreeWidgetItem(self.tree_widget)
            snippet_item.setText(0, snippet["timestamp"])
            snippet_item.setText(1, snippet["language"])
            snippet_item.setText(2, f"{len(snippet['code'])} chars")
            snippet_item.setData(0, Qt.ItemDataRole.UserRole, snippet)
    
    def show_snippet(self, item, column):
        """Display the selected code snippet in the code editor"""
        # Check if this is a snippet item (not a language header)
        snippet_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not snippet_data:
            return
        
        # Create a new tab for this snippet
        code_editor = CodeEditor()
        code_editor.setPlainText(snippet_data["code"])
        code_editor.set_language(snippet_data["language"])
        
        # Add tab with close button
        tab_title = f"{snippet_data['language']} - {snippet_data['timestamp']}"
        self.tab_widget.addTab(code_editor, tab_title)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
    
    def close_tab(self, index):
        """Close a tab when the close button is clicked"""
        if index != 0:  # Don't close the welcome tab
            self.tab_widget.removeTab(index)
    
    def open_filter_dialog(self):
        """Open dialog to filter snippets"""
        if not self.current_snippets:
            QMessageBox.information(self, "No Data", "No code snippets to filter. Process a video first.")
            return
        
        dialog = SnippetFilterDialog(self)
        if dialog.exec():
            filter_options = dialog.get_filter_options()
            self.apply_filters(filter_options)
    
    def apply_filters(self, options):
        """Apply filters to the snippets"""
        filtered_snippets = []
        unique_codes = set() if options["remove_duplicates"] else None
        
        for snippet in self.current_snippets:
            # Apply language filter
            if options["language"] and snippet["language"] != options["language"]:
                continue
            
            # Apply content filter
            if options["content"] and options["content"].lower() not in snippet["code"].lower():
                continue
            
            # Apply time filter
            # This is a simplified check - you may want a more sophisticated time comparison
            if snippet["timestamp"] < options["start_time"] or snippet["timestamp"] > options["end_time"]:
                continue
            
            # Apply duplicate filter
            if options["remove_duplicates"]:
                code_hash = hash(snippet["code"])
                if code_hash in unique_codes:
                    continue
                unique_codes.add(code_hash)
            
            filtered_snippets.append(snippet)
        
        # Update the tree with filtered results
        self.update_tree_view(filtered_snippets)
        self.status_bar.showMessage(f"Showing {len(filtered_snippets)} of {len(self.current_snippets)} snippets")
    
    def open_export_dialog(self):
        """Open dialog to export snippets"""
        if not self.current_snippets:
            QMessageBox.information(self, "No Data", "No code snippets to export. Process a video first.")
            return
        
        dialog = ExportDialog(self)
        if dialog.exec():
            export_options = dialog.get_export_options()
            self.export_snippets(export_options)
    
    def export_snippets(self, options):
        """Export snippets according to options."""
        try:
            export_path = options["export_path"]
            if not export_path:
                QMessageBox.warning(self, "Export Error", "Please select an export directory")
                return

            base_filename = self.current_file.split('.')[0] if self.current_file else f"code_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if "Python Files" in options["format"]:
                self.export_as_python_files(export_path, base_filename, options)
            elif "HTML" in options["format"]:
                self.export_as_html(export_path, base_filename, options)
            elif "Markdown" in options["format"]:
                self.export_as_markdown(export_path, base_filename, options)
            elif "Text Files" in options["format"]:
                self.export_as_text(export_path, base_filename, options)
            elif "JSON" in options["format"]:
                self.export_as_json(export_path, base_filename, options)

            QMessageBox.information(self, "Export Successful", f"Snippets exported to {export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export snippets: {str(e)}")
    
    def export_as_python_files(self, export_path, base_filename, options):
        """Export snippets as Python files"""
        if options["separate_files"]:
            for i, snippet in enumerate(self.current_snippets):
                if snippet["language"].lower() == "python":
                    filename = f"{base_filename}_{i+1}.py"
                    with open(os.path.join(export_path, filename), 'w') as f:
                        if options["include_timestamps"]:
                            f.write(f"# Timestamp: {snippet['timestamp']}\n")
                        if options["include_language"]:
                            f.write(f"# Language: {snippet['language']}\n")
                        f.write("\n")
                        f.write(snippet["code"])
        else:
            # Group by language and write Python snippets to a single file
            with open(os.path.join(export_path, f"{base_filename}.py"), 'w') as f:
                for i, snippet in enumerate(self.current_snippets):
                    if snippet["language"].lower() == "python":
                        f.write(f"# Snippet {i+1}\n")
                        if options["include_timestamps"]:
                            f.write(f"# Timestamp: {snippet['timestamp']}\n")
                        if options["include_language"]:
                            f.write(f"# Language: {snippet['language']}\n")
                        f.write("\n")
                        f.write(snippet["code"])
                        f.write("\n\n" + "#" * 80 + "\n\n")
    
    def export_as_html(self, export_path, base_filename, options):
        """Export snippets as HTML"""
        with open(os.path.join(export_path, f"{base_filename}.html"), 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Extracted Code Snippets</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        .snippet { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .snippet-header { margin-bottom: 10px; color: #555; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }
        .divider { margin: 40px 0; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <h1>Extracted Code Snippets</h1>
    <p>Extracted from: """ + (self.current_file or "video") + """</p>
""")
            
            for i, snippet in enumerate(self.current_snippets):
                f.write(f'<div class="snippet">\n')
                f.write(f'<div class="snippet-header">\n')
                f.write(f'<h2>Snippet {i+1}</h2>\n')
                
                if options["include_timestamps"]:
                    f.write(f'<p><strong>Timestamp:</strong> {snippet["timestamp"]}</p>\n')
                if options["include_language"]:
                    f.write(f'<p><strong>Language:</strong> {snippet["language"]}</p>\n')
                
                f.write('</div>\n')
                f.write(f'<pre><code>{snippet["code"]}</code></pre>\n')
                f.write('</div>\n')
                
                if i < len(self.current_snippets) - 1:
                    f.write('<div class="divider"></div>\n')
            
            f.write("""</body>
</html>""")
    
    def export_as_markdown(self, export_path, base_filename, options):
        """Export snippets as Markdown"""
        with open(os.path.join(export_path, f"{base_filename}.md"), 'w') as f:
            f.write("# Extracted Code Snippets\n\n")
            f.write(f"Extracted from: {self.current_file or 'video'}\n\n")
            
            for i, snippet in enumerate(self.current_snippets):
                f.write(f"## Snippet {i+1}\n\n")
                
                if options["include_timestamps"]:
                    f.write(f"**Timestamp:** {snippet['timestamp']}\n\n")
                if options["include_language"]:
                    f.write(f"**Language:** {snippet['language']}\n\n")
                
                f.write(f"```{snippet['language'].lower()}\n")
                f.write(snippet["code"])
                f.write("\n```\n\n")
                
                if i < len(self.current_snippets) - 1:
                    f.write("---\n\n")
    
    def export_as_text(self, export_path, base_filename, options):
        """Export snippets as plain text"""
        with open(os.path.join(export_path, f"{base_filename}.txt"), 'w') as f:
            f.write("EXTRACTED CODE SNIPPETS\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Extracted from: {self.current_file or 'video'}\n\n")
            
            for i, snippet in enumerate(self.current_snippets):
                f.write(f"SNIPPET {i+1}\n")
                f.write("-" * 80 + "\n")
                if options["include_timestamps"]:
                    f.write(f"Timestamp: {snippet['timestamp']}\n")
                if options["include_language"]:
                    f.write(f"Language: {snippet['language']}\n")
                f.write("\n")
                f.write(snippet["code"])
                f.write("\n\n")
    
    def export_as_json(self, export_path, base_filename, options):
        """Export snippets as JSON"""
        with open(os.path.join(export_path, f"{base_filename}.json"), 'w') as f:
            json_data = []
            for snippet in self.current_snippets:
                snippet_data = {
                    "timestamp": snippet["timestamp"],
                    "language": snippet["language"],
                    "code": snippet["code"]
                }
                if options["include_timestamps"]:
                    snippet_data["timestamp"] = snippet["timestamp"]
                if options["include_language"]:
                    snippet_data["language"] = snippet["language"]
                json_data.append(snippet_data)
            json.dump(json_data, f, indent=4)

    def processing_finished(self):
        """Handle completion of video processing"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Processing completed")
        self.display_results()

    def show_error(self, error_message):
        """Display an error message"""
        QMessageBox.critical(self, "Error", error_message)

    def view_database(self):
        """View all stored snippets in the database"""
        snippets = session.query(CodeSnippet).all()
        if not snippets:
            QMessageBox.information(self, "No Data", "No snippets found in the database.")
            return

        self.current_snippets = [
            {"timestamp": snippet.timestamp, "language": snippet.language, "code": snippet.code}
            for snippet in snippets
        ]
        self.update_tree_view(self.current_snippets)

    def show_about(self):
        """Display an About dialog"""
        QMessageBox.about(
            self,
            "About Professional Code Extractor",
            "Professional Code Extractor\n\n"
            "Version 1.0\n\n"
            "This application extracts code snippets from video tutorials and lectures, "
            "allowing you to filter, view, and export them in various formats."
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoCodeExtractorApp()
    window.show()
    sys.exit(app.exec())