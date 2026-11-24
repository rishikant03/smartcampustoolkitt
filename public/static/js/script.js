// Function to extract text client-side using PDF.js
async function extractTextFromPDF(file, onProgress) {
    if (!window.pdfjsLib) {
        throw new Error("PDF.js library is not loaded");
    }
    const arrayBuffer = await file.arrayBuffer();
    const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
    const pdf = await loadingTask.promise;
    let fullText = "";
    const totalPages = pdf.numPages;

    for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
        if (onProgress) {
            onProgress(pageNum, totalPages);
        }
        const page = await pdf.getPage(pageNum);
        const textContent = await page.getTextContent();
        const pageText = textContent.items.map(item => item.str).join(' ');
        fullText += pageText + '\n\n';
    }
    return fullText.trim();
}

document.addEventListener('DOMContentLoaded', () => {
    // ---- index.html: Drag and Drop Upload ----
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('pdf_file');
    const uploadForm = document.getElementById('upload-form');
    const fileInfo = document.getElementById('file-info');
    const filenameDisplay = document.getElementById('filename-display');
    const fileSizeTag = document.getElementById('file-size-tag');
    const loadingOverlay = document.getElementById('loading-overlay');
    const statusText = document.getElementById('loading-status-text');
    const progressEl = document.getElementById('loading-progress');
    const pasteForm = document.getElementById('paste-text-form');

    if (uploadArea && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => uploadArea.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('dragover'), false);
        });

        uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                showFileInfo(files[0]);
            }
        }, false);

        fileInput.addEventListener('change', function() {
            if (this.files.length) {
                showFileInfo(this.files[0]);
            }
        });

        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!fileInput.files.length) {
                alert("Please select a PDF file.");
                return;
            }

            const file = fileInput.files[0];
            const sizeMB = file.size / (1024 * 1024);

            if (loadingOverlay) loadingOverlay.style.display = 'flex';
            if (statusText) statusText.textContent = "Processing PDF document...";
            if (progressEl) progressEl.textContent = "";

            try {
                if (window.pdfjsLib) {
                    if (statusText) statusText.textContent = "Extracting text from PDF...";
                    const text = await extractTextFromPDF(file, (current, total) => {
                        if (progressEl) progressEl.textContent = `Page ${current} of ${total}`;
                    });

                    if (!text || text.length < 30) {
                        if (loadingOverlay) loadingOverlay.style.display = 'none';
                        alert("⚠️ No selectable text found in this PDF. It appears to be an image scan. Please upload a digital PDF with selectable text, or paste your notes directly in the 'Paste Notes / Text' tab.");
                        return;
                    }

                    if (statusText) statusText.textContent = "Uploading document text...";
                    if (progressEl) progressEl.textContent = "";

                    const response = await fetch('/upload-text', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            filename: file.name,
                            text: text
                        })
                    });

                    const data = await response.json();
                    if (response.ok && data.success) {
                        window.location.href = data.redirect_url;
                        return;
                    } else {
                        throw new Error(data.error || "Failed to process uploaded text.");
                    }
                } else {
                    // Fallback if PDF.js is unavailable
                    if (sizeMB > 4.5) {
                        if (loadingOverlay) loadingOverlay.style.display = 'none';
                        alert(`⚠️ This file is ${sizeMB.toFixed(1)} MB. Serverless functions allow up to 4.5 MB. Please use a smaller PDF or paste your notes in the 'Paste Notes / Text' tab.`);
                        return;
                    }
                    uploadForm.submit();
                }
            } catch (err) {
                console.error("Client extraction error:", err);
                if (sizeMB <= 4.5) {
                    if (statusText) statusText.textContent = "Uploading file directly to server...";
                    uploadForm.submit();
                } else {
                    if (loadingOverlay) loadingOverlay.style.display = 'none';
                    alert(`⚠️ Error processing PDF: ${err.message}. Since this file is ${sizeMB.toFixed(1)} MB (over the 4.5 MB serverless limit), please use the 'Paste Notes / Text' tab to paste the chapter text directly.`);
                }
            }
        });
    }

    if (pasteForm) {
        pasteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = (document.getElementById('paste-title').value || '').trim() || 'Chapter Notes';
            const text = (document.getElementById('paste-content').value || '').trim();

            if (!text || text.length < 30) {
                alert("Please paste at least 30 characters of chapter notes or content.");
                return;
            }

            if (loadingOverlay) loadingOverlay.style.display = 'flex';
            if (statusText) statusText.textContent = "Processing chapter content...";
            if (progressEl) progressEl.textContent = "";

            try {
                const response = await fetch('/upload-text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: title.toLowerCase().endsWith('.pdf') ? title : `${title}.pdf`,
                        text: text
                    })
                });

                const data = await response.json();
                if (response.ok && data.success) {
                    window.location.href = data.redirect_url;
                } else {
                    if (loadingOverlay) loadingOverlay.style.display = 'none';
                    alert(data.error || "Failed to process text.");
                }
            } catch (err) {
                if (loadingOverlay) loadingOverlay.style.display = 'none';
                alert(`Error: ${err.message}`);
            }
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function showFileInfo(file) {
        if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== "application/pdf") {
            alert("Please upload a PDF file.");
            fileInput.value = "";
            return;
        }
        uploadArea.style.display = 'none';
        fileInfo.style.display = 'block';
        filenameDisplay.textContent = `Selected: ${file.name}`;
        
        const sizeMB = file.size / (1024 * 1024);
        if (fileSizeTag) {
            fileSizeTag.textContent = `${sizeMB.toFixed(2)} MB`;
        }
    }

    // ---- settings.html: Generate Form Submission ----
    const generateForm = document.getElementById('generate-form');
    const aiLoadingOverlay = document.getElementById('ai-loading-overlay');

    if (generateForm) {
        generateForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (aiLoadingOverlay) aiLoadingOverlay.style.display = 'flex';
            
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
                    if (aiLoadingOverlay) aiLoadingOverlay.style.display = 'none';
                }
            } catch (error) {
                alert(`Network error: ${error.message}`);
                if (aiLoadingOverlay) aiLoadingOverlay.style.display = 'none';
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
