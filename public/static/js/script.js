document.addEventListener('DOMContentLoaded', () => {
    // ---- index.html: Drag and Drop Upload ----
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('pdf_file');
    const uploadForm = document.getElementById('upload-form');
    const fileInfo = document.getElementById('file-info');
    const filenameDisplay = document.getElementById('filename-display');
    const loadingOverlay = document.getElementById('loading-overlay');

    if (uploadArea && fileInput) {
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });

        // Handle dropped files
        uploadArea.addEventListener('drop', handleDrop, false);
        
        // Handle selected files via button
        fileInput.addEventListener('change', function() {
            if (this.files.length) {
                showFileInfo(this.files[0]);
            }
        });

        uploadForm.addEventListener('submit', () => {
            if (fileInput.files.length > 0) {
                loadingOverlay.style.display = 'flex';
            }
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        uploadArea.classList.add('dragover');
    }

    function unhighlight(e) {
        uploadArea.classList.remove('dragover');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length) {
            fileInput.files = files; // Assign files to input
            showFileInfo(files[0]);
        }
    }

    function showFileInfo(file) {
        if (file.type !== "application/pdf") {
            alert("Please upload a PDF file.");
            fileInput.value = ""; // Reset
            return;
        }
        uploadArea.style.display = 'none';
        fileInfo.style.display = 'block';
        filenameDisplay.textContent = `Selected: ${file.name}`;
    }

    // ---- settings.html: Generate Form Submission ----
    const generateForm = document.getElementById('generate-form');
    const aiLoadingOverlay = document.getElementById('ai-loading-overlay');

    if (generateForm) {
        generateForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            aiLoadingOverlay.style.display = 'flex';
            
            const formData = new FormData(generateForm);
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    window.location.href = `/preview/${data.paper_id}`;
                } else {
                    alert(`Error: ${data.error || 'Failed to generate paper'}`);
                    aiLoadingOverlay.style.display = 'none';
                }
            } catch (error) {
                alert(`Network error: ${error.message}`);
                aiLoadingOverlay.style.display = 'none';
            }
        });
    }
});

// ---- Global Navbar Kebab Menu Toggle ----
function toggleKebabMenu(event) {
    if (event) {
        event.stopPropagation();
    }
    const dropdown = document.getElementById('kebabDropdown');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('kebabDropdown');
    const btn = document.getElementById('kebabMenuBtn');
    if (dropdown && dropdown.classList.contains('show')) {
        if (!dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {
            dropdown.classList.remove('show');
        }
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const dropdown = document.getElementById('kebabDropdown');
        if (dropdown) dropdown.classList.remove('show');
    }
});
