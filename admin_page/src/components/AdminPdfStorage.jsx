import React, { useState, useRef, useCallback, useEffect } from 'react';
import { 
  FolderPlus, BookOpen, ChevronDown, UploadCloud, FileText, 
  Trash2, Plus, CheckCircle2, AlertCircle, Check, Search, 
  Download, Eye, HardDrive, Filter, X, ChevronRight,
  Menu, ShieldCheck, Folder, FolderOpen, ArrowLeft, Files
} from 'lucide-react';
import logoImg from '../assets/logo.png';

const INITIAL_SUBJECTS = [
  'Computer Science',
  'Mathematics',
  'Physics',
  'Chemistry',
  'Biology',
  'Economics',
  'Business Administration',
  'History',
  'Polity & Governance',
  'Literature'
];

const INITIAL_STORED_DOCS = [
  {
    id: 'doc-1',
    fileName: 'Data_Structures_Algorithm_Notes.pdf',
    subject: 'Computer Science',
    fileSize: '4.2 MB',
    uploadedAt: 'Today at 09:30 AM'
  },
  {
    id: 'doc-2',
    fileName: 'Operating_Systems_Core_Concepts.pdf',
    subject: 'Computer Science',
    fileSize: '6.1 MB',
    uploadedAt: 'Today at 10:15 AM'
  },
  {
    id: 'doc-3',
    fileName: 'Calculus_and_Linear_Algebra_Vol1.pdf',
    subject: 'Mathematics',
    fileSize: '8.7 MB',
    uploadedAt: 'Yesterday at 04:15 PM'
  },
  {
    id: 'doc-4',
    fileName: 'Macroeconomics_Theory_and_Policy.pdf',
    subject: 'Economics',
    fileSize: '5.4 MB',
    uploadedAt: 'Aug 27, 2026'
  }
];

const AdminPdfStorage = () => {
  // ── Navigation State ───────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'storage'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // ── Folder Repository State ────────────────────────────────────────────────
  const [selectedFolder, setSelectedFolder] = useState(null); // subject name or null

  // ── Subject & Upload States ────────────────────────────────────────────────
  const [subjects, setSubjects] = useState(INITIAL_SUBJECTS);
  const [selectedSubject, setSelectedSubject] = useState('');
  const [isSelectDropdownOpen, setIsSelectDropdownOpen] = useState(false);
  
  // Custom Subject Creation Mode
  const [isAddingNewSubject, setIsAddingNewSubject] = useState(false);
  const [newSubjectInput, setNewSubjectInput] = useState('');

  // PDF File Upload States
  const [pdfFile, setPdfFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // Stored PDF Documents Repository State
  const [storedDocs, setStoredDocs] = useState(INITIAL_STORED_DOCS);
  const [searchQuery, setSearchQuery] = useState('');

  const fileInputRef = useRef(null);
  const selectDropdownRef = useRef(null);

  // Close custom dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (selectDropdownRef.current && !selectDropdownRef.current.contains(e.target)) {
        setIsSelectDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Helper: Format File Size ──────────────────────────────────────────────
  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // ── Add New Subject Handler ───────────────────────────────────────────────
  const handleAddNewSubject = () => {
    const trimmed = newSubjectInput.trim();
    if (!trimmed) {
      setErrorMsg('Please enter a valid subject folder name.');
      setTimeout(() => setErrorMsg(null), 3000);
      return;
    }

    if (subjects.some(s => s.toLowerCase() === trimmed.toLowerCase())) {
      setErrorMsg('This subject folder already exists.');
      setTimeout(() => setErrorMsg(null), 3000);
      return;
    }

    const updated = [...subjects, trimmed].sort();
    setSubjects(updated);
    setSelectedSubject(trimmed);
    setNewSubjectInput('');
    setIsAddingNewSubject(false);
    setIsSelectDropdownOpen(false);
    setSuccessMsg(`Subject folder "${trimmed}" created successfully!`);
    setTimeout(() => setSuccessMsg(null), 3000);
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

  // ── Remove Selected PDF ───────────────────────────────────────────────────
  const handleRemoveFile = () => {
    setPdfFile(null);
    setUploadProgress(0);
    setErrorMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // ── Save & Store PDF Handler ──────────────────────────────────────────────
  const handleSaveDoc = () => {
    if (!selectedSubject || !pdfFile || isSaving) return;

    setIsSaving(true);

    setTimeout(() => {
      const newDoc = {
        id: `doc-${Date.now()}`,
        fileName: pdfFile.name,
        subject: selectedSubject,
        fileSize: pdfFile.size,
        uploadedAt: 'Just now'
      };

      setStoredDocs(prev => [newDoc, ...prev]);
      setIsSaving(false);
      setSuccessMsg(`PDF "${pdfFile.name}" saved into subject folder "${selectedSubject}"!`);

      // Reset file selection & open that subject folder in storage view
      handleRemoveFile();

      setTimeout(() => {
        setSuccessMsg(null);
        setSelectedFolder(selectedSubject);
        setActiveTab('storage');
      }, 1000);
    }, 800);
  };

  // ── Delete Stored PDF ──────────────────────────────────────────────────────
  const handleDeleteDoc = (docId) => {
    setStoredDocs(prev => prev.filter(d => d.id !== docId));
    setSuccessMsg('PDF document removed from subject folder.');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  // Delete an entire Subject Folder
  const handleDeleteFolder = (subjectName, e) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete folder "${subjectName}" and all its PDF contents?`)) {
      setSubjects(prev => prev.filter(s => s !== subjectName));
      setStoredDocs(prev => prev.filter(d => d.subject !== subjectName));
      if (selectedFolder === subjectName) setSelectedFolder(null);
      setSuccessMsg(`Folder "${subjectName}" deleted.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    }
  };

  // Helper to count files per subject
  const getDocsBySubject = (subjectName) => {
    return storedDocs.filter(d => d.subject === subjectName);
  };

  // Filtered Subject Folders List based on search
  const filteredFolders = subjects.filter(subjectName => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const matchesFolder = subjectName.toLowerCase().includes(q);
    const matchesFiles = getDocsBySubject(subjectName).some(d => d.fileName.toLowerCase().includes(q));
    return matchesFolder || matchesFiles;
  });

  // Docs inside currently opened folder
  const currentFolderDocs = selectedFolder 
    ? storedDocs.filter(d => d.subject === selectedFolder && d.fileName.toLowerCase().includes(searchQuery.toLowerCase()))
    : [];

  const isFormValid = Boolean(selectedSubject && pdfFile && !isUploading);

  return (
    <div className="admin-app-layout">
      {/* Sidebar Navigation */}
      <aside className={`admin-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <img src={logoImg} alt="Logo" className="sidebar-logo" />
          {!isSidebarCollapsed && (
            <div className="sidebar-brand-text">
              <span className="brand-name">ADMIN PORTAL</span>
              <span className="brand-sub">PDF Storage Center</span>
            </div>
          )}
        </div>

        <div className="sidebar-menu">
          <span className="menu-label">{isSidebarCollapsed ? 'MENU' : 'MANAGEMENT'}</span>
          
          {/* Nav Item 1: Upload PDF */}
          <button
            type="button"
            className={`nav-item ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
            title="Upload PDF"
          >
            <UploadCloud className="nav-icon" />
            {!isSidebarCollapsed && <span className="nav-text">Upload PDF</span>}
          </button>

          {/* Nav Item 2: PDF Storage Folders */}
          <button
            type="button"
            className={`nav-item ${activeTab === 'storage' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('storage');
              setSelectedFolder(null); // Reset to all folders view
            }}
            title="PDF Storage Folders"
          >
            <Folder className="nav-icon" />
            {!isSidebarCollapsed && (
              <div className="nav-text-group">
                <span className="nav-text">PDF Storage</span>
                <span className="nav-badge">{storedDocs.length} Docs</span>
              </div>
            )}
          </button>
        </div>

        {/* Sidebar Footer */}
        <div className="sidebar-footer">
          <div className="system-status">
            <span className="pulse-dot"></span>
            {!isSidebarCollapsed && <span className="status-text">System Active</span>}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="admin-main-wrapper">
        {/* Top Navbar */}
        <header className="admin-topbar">
          <div className="topbar-title-group">
            <button
              type="button"
              className="toggle-sidebar-btn"
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              title="Toggle Sidebar"
            >
              <Menu size={20} />
            </button>
            <h2 className="topbar-title">
              {activeTab === 'upload' 
                ? 'Upload & Assign PDF to Subject Folder' 
                : selectedFolder 
                ? `Subject Folder: ${selectedFolder}` 
                : 'Subject Folders Repository'}
            </h2>
          </div>
        </header>

        {/* Page Content */}
        <main className="admin-content">
          {/* Toast Notifications */}
          {errorMsg && (
            <div className="toast error">
              <AlertCircle className="toast-icon" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="toast success">
              <CheckCircle2 className="toast-icon text-success" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* ======================================================================== */}
          {/* SECTION 1: UPLOAD PDF */}
          {/* ======================================================================== */}
          {activeTab === 'upload' && (
            <div className="content-card fade-in">
              <div className="card-header">
                <img src={logoImg} alt="Logo" style={{ height: '52px', width: 'auto', objectFit: 'contain', flexShrink: 0 }} />
                <div>
                  <h2 className="card-title">Upload PDF into Subject Folder</h2>
                  <p className="card-description">
                    Select a subject folder or create a new one, attach your PDF file, and save it to storage.
                  </p>
                </div>
              </div>

              <form className="form-body" onSubmit={(e) => e.preventDefault()}>
                {/* 1. Subject Selection & Creation */}
                <div className="form-group">
                  <div className="form-label-row">
                    <label htmlFor="subjectSelect" className="form-label">
                      <span>1. Select or Create Subject Folder</span>
                      <span className="required-star">*</span>
                    </label>

                    {!isAddingNewSubject && (
                      <button
                        type="button"
                        className="btn-create-subject-pill"
                        onClick={() => setIsAddingNewSubject(true)}
                      >
                        <Plus size={14} /> Add New Subject Folder
                      </button>
                    )}
                  </div>

                  {/* Add New Subject Mode */}
                  {isAddingNewSubject ? (
                    <div className="new-subject-box">
                      <div className="input-with-icon">
                        <BookOpen className="input-icon" />
                        <input
                          type="text"
                          className="custom-input"
                          placeholder="Enter new subject folder name..."
                          value={newSubjectInput}
                          onChange={(e) => setNewSubjectInput(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleAddNewSubject()}
                          autoFocus
                        />
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          className="btn-secondary-sm"
                          onClick={() => {
                            setIsAddingNewSubject(false);
                            setNewSubjectInput('');
                          }}
                        >
                          <X size={14} /> Cancel
                        </button>
                        <button
                          type="button"
                          className="btn-primary-sm"
                          onClick={handleAddNewSubject}
                        >
                          <Check size={14} /> Create Folder
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Modern Custom Subject Dropdown Menu Component */
                    <div className="custom-dropdown-container" ref={selectDropdownRef}>
                      <button
                        type="button"
                        className={`custom-dropdown-trigger ${isSelectDropdownOpen ? 'open' : ''} ${selectedSubject ? 'selected' : ''}`}
                        onClick={() => setIsSelectDropdownOpen(!isSelectDropdownOpen)}
                      >
                        <div className="trigger-left">
                          <Folder className="trigger-folder-icon" />
                          <span className="trigger-text">
                            {selectedSubject ? selectedSubject : 'Select Subject Folder...'}
                          </span>
                        </div>
                        <ChevronDown className={`trigger-chevron ${isSelectDropdownOpen ? 'rotated' : ''}`} />
                      </button>

                      {isSelectDropdownOpen && (
                        <div className="custom-dropdown-menu">
                          <div className="dropdown-menu-header">
                            <span>AVAILABLE SUBJECT FOLDERS</span>
                            <span className="count-tag">{subjects.length} Folders</span>
                          </div>

                          <div className="dropdown-menu-list">
                            {subjects.map((subj) => {
                              const count = getDocsBySubject(subj).length;
                              const isSelected = selectedSubject === subj;
                              return (
                                <button
                                  key={subj}
                                  type="button"
                                  className={`dropdown-menu-item ${isSelected ? 'selected' : ''}`}
                                  onClick={() => {
                                    setSelectedSubject(subj);
                                    setIsSelectDropdownOpen(false);
                                  }}
                                >
                                  <div className="item-left">
                                    <Folder className="item-folder-icon" />
                                    <span className="item-title">{subj}</span>
                                  </div>
                                  <span className="item-count-badge">
                                    {count} {count === 1 ? 'file' : 'files'}
                                  </span>
                                </button>
                              );
                            })}
                          </div>

                          <div className="dropdown-menu-footer">
                            <button
                              type="button"
                              className="btn-dropdown-add"
                              onClick={() => {
                                setIsSelectDropdownOpen(false);
                                setIsAddingNewSubject(true);
                              }}
                            >
                              <Plus size={14} /> Create New Subject Folder
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 2. Drag & Drop PDF Upload Area */}
                <div className="form-group">
                  <label className="form-label">
                    <span>2. Upload PDF File</span>
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
                              <CheckCircle2 className="chip-icon" /> Ready to Store
                            </span>
                          </div>
                          <div className="file-meta">
                            <span className="meta-item">{pdfFile.size}</span>
                            <span className="meta-dot">•</span>
                            <span className="meta-item text-success">Target Folder: {selectedSubject || 'Unassigned'}</span>
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

                {/* Primary Save & Store Action */}
                <div className="form-actions">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={!isFormValid || isSaving}
                    onClick={handleSaveDoc}
                  >
                    {isSaving ? (
                      <>
                        <div className="btn-spinner"></div>
                        <span>Saving to Folder...</span>
                      </>
                    ) : (
                      <>
                        <FolderPlus className="btn-icon" />
                        <span>Save &amp; Store PDF in Folder</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* ======================================================================== */}
          {/* SECTION 2: FOLDER-BASED PDF STORAGE REPOSITORY */}
          {/* ======================================================================== */}
          {activeTab === 'storage' && (
            <div className="repository-section fade-in">
              {/* Toolbar & Search */}
              <div className="repo-header">
                {selectedFolder ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button
                      type="button"
                      className="btn-secondary-sm"
                      onClick={() => setSelectedFolder(null)}
                    >
                      <ArrowLeft size={16} /> Back to All Folders
                    </button>
                    <div className="folder-title-badge">
                      <FolderOpen style={{ color: '#f59e0b' }} size={20} />
                      <span style={{ fontWeight: '800', color: '#0f2242', fontSize: '1.1rem' }}>{selectedFolder}</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div className="header-icon-box">
                      <Folder className="repo-icon" />
                    </div>
                    <div>
                      <h3 className="repo-title">Subject Folders Repository</h3>
                      <p className="repo-subtitle">Click on any subject folder to view its stored PDF files</p>
                    </div>
                  </div>
                )}

                <button
                  type="button"
                  className="btn-primary-sm"
                  onClick={() => {
                    setActiveTab('upload');
                    if (selectedFolder) setSelectedSubject(selectedFolder);
                  }}
                >
                  <Plus size={14} /> Upload PDF to Folder
                </button>
              </div>

              {/* Search Toolbar */}
              <div className="repo-toolbar">
                <div className="search-box">
                  <Search className="search-icon" />
                  <input
                    type="text"
                    className="search-input"
                    placeholder={selectedFolder ? `Search files inside ${selectedFolder}...` : "Search subject folders or file names..."}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>

              {/* VIEW A: ALL SUBJECT FOLDERS GRID */}
              {!selectedFolder && (
                <div className="folders-grid">
                  {filteredFolders.length === 0 ? (
                    <div className="empty-docs">
                      <Folder className="empty-icon" />
                      <p className="empty-title">No subject folders found</p>
                      <p className="empty-subtitle">Create a subject folder in the Upload section to begin storing PDFs.</p>
                    </div>
                  ) : (
                    filteredFolders.map((subjName) => {
                      const docsInSubj = getDocsBySubject(subjName);
                      return (
                        <div
                          key={subjName}
                          className="folder-card"
                          onClick={() => setSelectedFolder(subjName)}
                        >
                          <div className="folder-card-header">
                            <div className="folder-icon-box">
                              <Folder className="folder-svg" />
                            </div>
                            <button
                              type="button"
                              className="btn-delete-folder"
                              title="Delete Subject Folder"
                              onClick={(e) => handleDeleteFolder(subjName, e)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>

                          <div className="folder-card-body">
                            <h4 className="folder-name">{subjName}</h4>
                            <p className="folder-doc-count">
                              <Files size={13} /> {docsInSubj.length} {docsInSubj.length === 1 ? 'PDF File' : 'PDF Files'}
                            </p>
                          </div>

                          <div className="folder-card-footer">
                            <span className="open-folder-text">Open Folder</span>
                            <ChevronRight size={16} className="chevron-icon" />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* VIEW B: INSIDE SELECTED SUBJECT FOLDER (FILE LIST) */}
              {selectedFolder && (
                <div className="folder-inside-view">
                  <div className="inside-folder-meta-banner">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FolderOpen style={{ color: '#f59e0b' }} size={22} />
                      <div>
                        <h4 style={{ fontSize: '1rem', fontWeight: '800', color: '#0f2242' }}>{selectedFolder}</h4>
                        <p style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          Contains {currentFolderDocs.length} PDF {currentFolderDocs.length === 1 ? 'document' : 'documents'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {currentFolderDocs.length === 0 ? (
                    <div className="empty-docs">
                      <FileText className="empty-icon" />
                      <p className="empty-title">This subject folder is empty</p>
                      <p className="empty-subtitle">Upload a PDF file to store it inside the "{selectedFolder}" folder.</p>
                      <button
                        type="button"
                        className="btn-primary-sm"
                        style={{ marginTop: '12px' }}
                        onClick={() => {
                          setSelectedSubject(selectedFolder);
                          setActiveTab('upload');
                        }}
                      >
                        <Plus size={14} /> Upload PDF to {selectedFolder}
                      </button>
                    </div>
                  ) : (
                    <div className="docs-list">
                      {currentFolderDocs.map((doc) => (
                        <div key={doc.id} className="doc-row">
                          <div className="doc-main">
                            <div className="doc-icon-box">
                              <FileText className="doc-file-icon" />
                            </div>
                            <div className="doc-info">
                              <div className="doc-name-row">
                                <h4 className="doc-name">{doc.fileName}</h4>
                                <span className="subject-tag">{doc.subject}</span>
                              </div>
                              <div className="doc-meta">
                                <span>{doc.fileSize}</span>
                                <span className="meta-dot">•</span>
                                <span>Uploaded: {doc.uploadedAt}</span>
                              </div>
                            </div>
                          </div>

                          <div className="doc-actions">
                            <button
                              type="button"
                              className="btn-icon-action"
                              title="View PDF"
                              onClick={() => alert(`Opening "${doc.fileName}" from "${doc.subject}" folder`)}
                            >
                              <Eye size={16} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon-action"
                              title="Download PDF"
                              onClick={() => alert(`Downloading "${doc.fileName}"`)}
                            >
                              <Download size={16} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon-danger"
                              title="Delete File"
                              onClick={() => handleDeleteDoc(doc.id)}
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default AdminPdfStorage;
