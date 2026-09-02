import React, { useState, useRef, useCallback } from 'react';
import { 
  BookOpen, ChevronDown, UploadCloud, FileText, 
  Trash2, Sparkles, CheckCircle2, AlertCircle, Check, RotateCcw 
} from 'lucide-react';
import logoImg from '../assets/logo.png';

const SUBJECT_OPTIONS = [
  { id: 'computer_science', label: 'Computer Science' },
  { id: 'mathematics', label: 'Mathematics' },
  { id: 'physics', label: 'Physics' },
  { id: 'chemistry', label: 'Chemistry' },
  { id: 'biology', label: 'Biology' },
  { id: 'economics', label: 'Economics' },
  { id: 'business_administration', label: 'Business Administration' },
  { id: 'history', label: 'History' },
  { id: 'literature', label: 'Literature' }
];

const AdminPdfUpload = () => {
  // ── Component States ───────────────────────────────────────────────────────
  const [subject, setSubject] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedResult, setGeneratedResult] = useState(null);

  const fileInputRef = useRef(null);

  // ── Helper: Format File Size ──────────────────────────────────────────────
  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // ── PDF File Validation & Processing ──────────────────────────────────────
  const processFile = useCallback((file) => {
    if (!file) return;

    // Validate PDF file format
    const isPdfType = file.type === 'application/pdf';
    const isPdfExt = file.name.toLowerCase().endsWith('.pdf');

    if (!isPdfType && !isPdfExt) {
      setErrorMsg('Invalid file format. Only PDF files (.pdf) are accepted.');
      setTimeout(() => setErrorMsg(null), 4000);
      return;
    }

    setErrorMsg(null);
    setIsUploading(true);
    setUploadProgress(0);

    // Simulate progress animation
    let progress = 0;
    const interval = setInterval(() => {
      progress += 25;
      setUploadProgress(progress);

      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          setIsUploading(false);
          setPdfFile({
            fileObj: file,
            name: file.name,
            size: formatFileSize(file.size),
            rawSize: file.size,
            uploadedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          });
        }, 200);
      }
    }, 90);
  }, []);

  // ── Drag & Drop Event Handlers ──────────────────────────────────────────────
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles && droppedFiles.length > 0) {
      processFile(droppedFiles[0]);
    }
  };

  // ── Remove PDF File ────────────────────────────────────────────────────────
  const handleRemoveFile = () => {
    setPdfFile(null);
    setUploadProgress(0);
    setErrorMsg(null);
    setGeneratedResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // ── Handle MCQ Generation CTA ──────────────────────────────────────────────
  const handleGenerate = () => {
    if (!subject || !pdfFile || isGenerating) return;

    setIsGenerating(true);

    // Simulate MCQ Generation delay
    setTimeout(() => {
      setIsGenerating(false);
      const selectedSubjectObj = SUBJECT_OPTIONS.find(s => s.id === subject);
      setGeneratedResult({
        subjectLabel: selectedSubjectObj ? selectedSubjectObj.label : subject,
        fileName: pdfFile.name,
        questionCount: 5,
        timestamp: new Date().toLocaleTimeString()
      });
    }, 1500);
  };

  // Reset all fields
  const handleReset = () => {
    setSubject('');
    handleRemoveFile();
  };

  // Check if primary CTA should be enabled
  const isFormValid = Boolean(subject && pdfFile && !isUploading);

  return (
    <div className="admin-layout">
      {/* Top Navigation Header */}
      <header className="admin-header">
        <div className="header-container">
          <div className="brand">
            <img src={logoImg} alt="Academy Logo" className="h-10 w-auto object-contain shrink-0" />
            <div className="brand-info">
              <h1 className="brand-title">Admin Dashboard</h1>
              <span className="brand-subtitle">MCQ Generator System</span>
            </div>
          </div>
          <div className="header-actions">
            <span className="status-badge">
              <span className="pulse-dot"></span> System Ready
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="main-container">
        <div className="content-card">
          <div className="card-header">
            <img src={logoImg} alt="Academy Logo" className="h-14 w-auto object-contain shrink-0" />
            <div>
              <h2 className="card-title">Generate MCQs from PDF</h2>
              <p className="card-description">
                Select a subject and upload a document to automatically generate multiple-choice practice questions.
              </p>
            </div>
          </div>

          <form className="form-body" onSubmit={(e) => e.preventDefault()}>
            {/* Error Toast Notification */}
            {errorMsg && (
              <div className="toast error">
                <AlertCircle className="toast-icon" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* 1. Subject Dropdown */}
            <div className="form-group">
              <label htmlFor="subjectSelect" className="form-label">
                <span>1. Select Subject</span>
                <span className="required-star">*</span>
              </label>
              <div className="select-wrapper">
                <BookOpen className="select-icon" />
                <select
                  id="subjectSelect"
                  className="custom-select"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  required
                >
                  <option value="" disabled>Select Subject</option>
                  {SUBJECT_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="select-chevron" />
              </div>
            </div>

            {/* 2. Drag & Drop PDF Upload Area */}
            <div className="form-group">
              <label className="form-label">
                <span>2. Upload PDF Document</span>
                <span className="required-star">*</span>
              </label>

              {/* Hidden File Input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="file-input"
                onChange={(e) => processFile(e.target.files[0])}
              />

              {/* Empty & Drag-Over Dropzone */}
              {!pdfFile && !isUploading && (
                <div
                  className={`dropzone ${isDragging ? 'drag-over' : ''}`}
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  tabIndex={0}
                  role="button"
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInputRef.current?.click()}
                >
                  <div className="dropzone-content">
                    <div className="upload-icon-wrapper">
                      <UploadCloud className="upload-icon" />
                    </div>
                    <h3 className="dropzone-heading">Drag &amp; drop your PDF here</h3>
                    <span className="dropzone-divider">or</span>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                    >
                      <FileText className="btn-icon" />
                      <span>Choose PDF</span>
                    </button>
                    <p className="dropzone-hint">Only PDF files are supported (Max size: 25MB)</p>
                  </div>
                </div>
              )}

              {/* Uploading Progress State */}
              {isUploading && (
                <div className="uploading-state">
                  <div className="upload-spinner-box">
                    <div className="spinner"></div>
                  </div>
                  <div className="uploading-info">
                    <span className="uploading-text">Reading &amp; validating PDF file...</span>
                    <div className="progress-bar-bg">
                      <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }}></div>
                    </div>
                  </div>
                </div>
              )}

              {/* Uploaded File Details Card */}
              {pdfFile && !isUploading && (
                <div className="file-card">
                  <div className="file-info-main">
                    <div className="file-badge">
                      <FileText className="pdf-file-icon" />
                    </div>
                    <div className="file-details">
                      <div className="file-title-row">
                        <span className="file-name">{pdfFile.name}</span>
                        <span className="status-chip success">
                          <CheckCircle2 className="chip-icon" /> Uploaded
                        </span>
                      </div>
                      <div className="file-meta">
                        <span className="meta-item">{pdfFile.size}</span>
                        <span className="meta-dot">•</span>
                        <span className="meta-item text-success">PDF Ready</span>
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-remove"
                    onClick={handleRemoveFile}
                    title="Remove PDF"
                  >
                    <Trash2 className="remove-icon" />
                  </button>
                </div>
              )}
            </div>

            {/* Primary Generate MCQs Button */}
            <div className="form-actions">
              <button
                type="button"
                className="btn-primary"
                disabled={!isFormValid || isGenerating}
                onClick={handleGenerate}
              >
                {isGenerating ? (
                  <>
                    <div className="btn-spinner"></div>
                    <span>Generating MCQs...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="btn-icon" />
                    <span>Generate MCQs</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Results Card Preview */}
        {generatedResult && (
          <div className="result-card">
            <div className="result-header">
              <div className="result-title-group">
                <div className="success-badge">
                  <Check className="check-icon" />
                </div>
                <div>
                  <h3 className="result-title">MCQs Successfully Generated</h3>
                  <p className="result-subtitle">
                    Generated {generatedResult.questionCount} questions for {generatedResult.subjectLabel} from "{generatedResult.fileName}"
                  </p>
                </div>
              </div>
              <button type="button" className="btn-outline-sm" onClick={handleReset}>
                <RotateCcw className="btn-icon" /> Reset &amp; New
              </button>
            </div>

            <div className="questions-list">
              <div className="q-item">
                <span className="q-num">Q1</span>
                <div className="q-body">
                  <p className="q-text">
                    Which of the following best describes the core principle outlined in {generatedResult.fileName}?
                  </p>
                  <div className="q-options">
                    <div className="opt-chip correct">
                      <CheckCircle2 className="opt-icon" /> Option A: Primary structural specification &amp; logic models
                    </div>
                    <div className="opt-chip">Option B: Secondary parameter overrides</div>
                    <div className="opt-chip">Option C: Legacy configuration handlers</div>
                    <div className="opt-chip">Option D: External dependency routines</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default AdminPdfUpload;
