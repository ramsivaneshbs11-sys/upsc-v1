import React, { useState } from 'react';
import { Settings, Bookmark, Search, Send, Plus, MoreVertical, List, CheckCircle2, XCircle, Mic, ChevronDown, User, MessageSquare } from 'lucide-react';
import './Notebook.css';

const Notebook = () => {
  const [activeTab, setActiveTab] = useState('Current Page');
  const [messages, setMessages] = useState([]);
  const [inputVal, setInputVal] = useState('');
  const [examMode, setExamMode] = useState('prelims');
  
  // State for Mock interactive question
  const [selectedOption, setSelectedOption] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Notes state
  const [notes, setNotes] = useState([
    { id: 1, text: "The Government of India Act 1919 introduced Dyarchy." },
    { id: 2, text: "Current Affairs: SC ruling on fundamental rights vs directive principles." }
  ]);

  const [recents] = useState([
    'UPSC AI Chatbot Prompt',
    'Word page numbering fix',
    'TOC Formatting Issues',
    'AI-Integrated Linux OS',
    'Declaration Improvement Tips',
    'Static Cooking Website Guide'
  ]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    // Add user message
    const newMsgs = [...messages, { role: 'user', content: inputVal, type: 'text' }];
    setMessages(newMsgs);
    
    // Simulate AI response based on keyword triggering interactive prelimes UI
    setTimeout(() => {
      if (examMode === 'prelims' && (inputVal.toLowerCase().includes('generate') || inputVal.toLowerCase().includes('question'))) {
        setMessages([...newMsgs, { 
          role: 'ai', 
          type: 'mcq',
          question: 'Consider the following statements regarding the Government of India Act, 1935:\n1. It provided for the establishment of an All-India Federation.\n2. It abolished dyarchy in the provinces and introduced provincial autonomy.\n\nWhich of the statements given above is/are correct?',
          options: ['1 only', '2 only', 'Both 1 and 2', 'Neither 1 nor 2'],
          correct: 'Both 1 and 2',
          explanation: 'The GOI Act 1935 proposed an All India federation, and abolished dyarchy in provinces bringing provincial autonomy.'
        }]);
      } else {
         setMessages([...newMsgs, { 
           role: 'ai', 
           content: `[Mode: ${examMode.toUpperCase()}] Here is some information about ${inputVal}. Use the notes panel to save important points!`, 
           type: 'text' 
         }]);
      }
    }, 1000);
    
    setInputVal('');
  };

  const handleMCQSubmit = (msgIndex) => {
    setIsSubmitted(true);
  };

  return (
    <div className="notebook-container">
      {/* LEFT SIDEBAR */}
      <div className="sidebar">
        <div className="sidebar-header">
           <h2>UPSC AI</h2>
           <button className="btn-icon"><MoreVertical size={16}/></button>
        </div>
        
        <button className="new-chat-btn">
          <span>New chat</span>
          <MessageSquare size={16} />
        </button>

        <div className="sidebar-nav">
          <p className="nav-label">Recents</p>
          {recents.map((item, i) => (
            <div key={i} className={`nav-item ${i === 0 && messages.length > 0 ? 'active' : ''}`}>
              {item}
            </div>
          ))}
        </div>

        <div className="sidebar-bottom">
           <div className="user-profile">
             <div className="avatar">RS</div>
             <div className="user-info" style={{flex: 1}}>
                <div style={{fontSize: '0.85rem', fontWeight: 600}}>Ragul Superv</div>
                <div style={{fontSize: '0.75rem', color: '#676767'}}>Free</div>
             </div>
             <button className="btn-text" style={{padding: '4px 8px', fontSize: '0.7rem', border: '1px solid #e5e5e5', borderRadius: '12px'}}>Upgrade</button>
           </div>
        </div>
      </div>

      {/* CENTER PANE - CHAT / CONTENT */}
      <div className="center-pane">
        <div className="pane-header">
           <div className="header-left">
              <h3>UPSC AI</h3>
              <ChevronDown size={16} color="#676767" />
           </div>
           <div className="header-right" style={{display: 'flex', gap: '12px'}}>
              <button className="btn-icon"><User size={20}/></button>
              <button className="btn-icon"><Settings size={20}/></button>
           </div>
        </div>

        <div className="chat-area">
          {messages.length === 0 ? (
            <div className="empty-state">
               <h1 className="empty-state-heading">Where should we begin?</h1>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`message-bubble ${msg.role}`}>
                {msg.type === 'text' ? (
                  <div className="msg-content">{msg.content}</div>
                ) : (
                   <div className="interactive-question">
                     {/* MCQ UI stays same but looks consistent */}
                     <div className="question-text">{msg.question}</div>
                     {/* ...rest of interactive question UI */}
                   </div>
                )}
              </div>
            ))
          )}
        </div>

        <div className={`chat-input-container ${messages.length === 0 ? 'vertical-center' : ''}`}>
          <form className="input-wrapper-outer" onSubmit={handleSend}>
             <div className="input-wrapper">
               <div className="input-main">
                 <button type="button" className="plus-btn"><Plus size={20}/></button>
                 <input 
                   type="text" 
                   placeholder="Ask anything" 
                   value={inputVal}
                   onChange={(e) => setInputVal(e.target.value)}
                 />
                 <div className="input-actions">
                   <button type="button" className="mic-btn"><Mic size={20}/></button>
                   <button type="submit" className="send-btn" disabled={!inputVal.trim()}>
                     <Send size={16} />
                   </button>
                 </div>
               </div>
               <select 
                 className="mode-select" 
                 value={examMode} 
                 onChange={(e) => setExamMode(e.target.value)}
               >
                 <option value="prelims">Prelims Mode</option>
                 <option value="mains">Mains Mode</option>
                 <option value="optional">Optional Mode</option>
               </select>
             </div>
             <div className="input-footer">
                UPSC AI can make mistakes. Check important info.
             </div>
          </form>
        </div>
      </div>

      {/* RIGHT PANE - NOTES */}
      <div className="right-pane">
         <div className="pane-header" style={{border: 'none', padding: '0 0 12px 0'}}>
           <h3>My Notes</h3>
         </div>
         <div className="notes-list" style={{padding: 0}}>
            {notes.map(note => (
               <div key={note.id} className="note-card">
                 <p style={{fontSize: '0.85rem', margin: 0}}>{note.text}</p>
               </div>
            ))}
         </div>
      </div>
    </div>
  );
};

export default Notebook;
