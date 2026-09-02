// ==========================================================================
// Admin PDF Upload UI — Interactive Application Logic
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // DOM Elements
  const subjectSelect = document.getElementById('subjectSelect');
  const fileInput = document.getElementById('fileInput');
  const dropzone = document.getElementById('dropzone');
  const browseBtn = document.getElementById('browseBtn');
  const uploadingState = document.getElementById('uploadingState');
  const progressBar = document.getElementById('progressBar');
  const fileCard = document.getElementById('fileCard');
  const fileNameDisplay = document.getElementById('fileName');
  const fileSizeDisplay = document.getElementById('fileSize');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const generateBtn = document.getElementById('generateBtn');
  const generateBtnText = document.getElementById('generateBtnText');
  const btnSpinner = document.getElementById('btnSpinner');
  const toastNotification = document.getElementById('toastNotification');
  const toastMessage = document.getElementById('toastMessage');
  const resultCard = document.getElementById('resultCard');
  const resultSubtitle = document.getElementById('resultSubtitle');
  const resetBtn = document.getElementById('resetBtn');

  // Application State
  let currentFile = null;

  // --------------------------------------------------------------------------
  // Helper Functions
  // --------------------------------------------------------------------------

  // Formatted File Size (Bytes to KB / MB)
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Toast Notification Trigger
  const showToast = (message, type = 'error') => {
    toastMessage.textContent = message;
    toastNotification.className = `toast ${type}`;
    
    // Refresh Lucide icon if needed
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
      toastNotification.className = 'toast hidden';
    }, 4000);
  };

  // Enable / Disable Generate Button based on criteria
  const validateForm = () => {
    const isSubjectSelected = subjectSelect.value && subjectSelect.value.trim() !== '';
    const isFileUploaded = currentFile !== null;

    if (isSubjectSelected && isFileUploaded) {
      generateBtn.disabled = false;
    } else {
      generateBtn.disabled = true;
    }
  };

  // PDF File Validation
  const isValidPDF = (file) => {
    if (!file) return false;
    const isPDFType = file.type === 'application/pdf';
    const isPDFExtension = file.name.toLowerCase().endsWith('.pdf');
    return isPDFType || isPDFExtension;
  };

  // --------------------------------------------------------------------------
  // File Upload Handling
  // --------------------------------------------------------------------------

  const handleFileSelection = (file) => {
    if (!file) return;

    // Reject non-PDF files
    if (!isValidPDF(file)) {
      showToast('Invalid file format. Only PDF files (.pdf) are accepted.', 'error');
      return;
    }

    // Hide empty dropzone and toast
    dropzone.classList.add('hidden');
    toastNotification.classList.add('hidden');

    // Show simulated upload progress state
    uploadingState.classList.remove('hidden');
    progressBar.style.width = '0%';

    let progress = 0;
    const interval = setInterval(() => {
      progress += 25;
      progressBar.style.width = `${progress}%`;

      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          // Finish upload progress
          uploadingState.classList.add('hidden');
          
          // Populate & show uploaded file details card
          currentFile = file;
          fileNameDisplay.textContent = file.name;
          fileSizeDisplay.textContent = formatFileSize(file.size);
          fileCard.classList.remove('hidden');

          // Re-evaluate form state
          validateForm();

          if (window.lucide) lucide.createIcons();
        }, 200);
      }
    }, 100);
  };

  const removeFile = () => {
    currentFile = null;
    fileInput.value = '';
    
    // Toggle UI elements back to empty state
    fileCard.classList.add('hidden');
    uploadingState.classList.add('hidden');
    dropzone.classList.remove('hidden');
    resultCard.classList.add('hidden');

    validateForm();
  };

  // --------------------------------------------------------------------------
  // Event Listeners
  // --------------------------------------------------------------------------

  // Subject Dropdown Change
  subjectSelect.addEventListener('change', () => {
    validateForm();
  });

  // Browse Button & Dropzone Click Events
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  // File Input Change
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileSelection(file);
    }
  });

  // Drag and Drop Events
  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('drag-over');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles && droppedFiles.length > 0) {
      handleFileSelection(droppedFiles[0]);
    }
  });

  // Remove File Button
  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    removeFile();
  });

  // Generate MCQs Button Action
  generateBtn.addEventListener('click', () => {
    if (generateBtn.disabled || !currentFile || !subjectSelect.value) return;

    // Loading State
    generateBtn.disabled = true;
    generateBtnText.textContent = 'Generating MCQs...';
    btnSpinner.classList.remove('hidden');

    // Simulate API delay (~1.4s)
    setTimeout(() => {
      // Revert Button State
      generateBtnText.textContent = 'Generate MCQs';
      btnSpinner.classList.add('hidden');
      generateBtn.disabled = false;

      // Show Result Card Preview
      const selectedSubjectText = subjectSelect.options[subjectSelect.selectedIndex].text;
      resultSubtitle.textContent = `Generated 5 practice questions for ${selectedSubjectText} from "${currentFile.name}"`;
      resultCard.classList.remove('hidden');

      // Scroll smoothly to results
      resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      if (window.lucide) lucide.createIcons();
    }, 1400);
  });

  // Reset Button
  resetBtn.addEventListener('click', () => {
    resultCard.classList.add('hidden');
    removeFile();
    subjectSelect.selectedIndex = 0;
    validateForm();
  });
});
