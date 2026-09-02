import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, 
  FileText, 
  Target, 
  Newspaper, 
  GitBranch, 
  Users, 
  BookOpen, 
  Sun, 
  Moon, 
  Zap, 
  Globe, 
  Ribbon, 
  Search, 
  Send, 
  History,
  Sparkles
} from 'lucide-react';

const UPSCMain = () => {
  const [darkMode, setDarkMode] = useState(false);
  const [activeTab, setActiveTab] = useState('Questions');
  const [activeSidebar, setActiveSidebar] = useState('Ask UPSC Ai');

  // Colors based on prompt
  const colors = {
    light: {
      sidebarActive: '#A2411E',
      accent: '#7E121D',
      text: '#000000',
      bg: 'bg-gray-50',
      card: 'bg-white/70',
    },
    dark: {
      sidebarActive: '#F97316',
      accent: '#B91C1C',
      text: '#ffffff',
      bg: 'bg-[#0a0a0a]',
      card: 'bg-[#1a1a1a]/70',
    }
  };

  const currentTheme = darkMode ? colors.dark : colors.light;

  const sidebarItems = [
    { name: 'Ask UPSC Ai', icon: MessageSquare, section: 'AI TOOLS' },
    { name: 'MCQ Practice AI', icon: Target, section: 'AI TOOLS' },
    { name: 'Daily News', icon: Newspaper, section: 'AI TOOLS' },
    { name: 'Mind Map', icon: GitBranch, section: 'AI TOOLS' },
    { name: 'Chat Room', icon: Users, section: 'AI TOOLS' },
  ];

  const suggestionCards = [
    { text: 'Explain the role of RBI in Indian Economy', color: 'bg-orange-500' },
    { text: 'What is biodiversity and its importance?', color: 'bg-green-500' },
    { text: 'Explain the importance of Himalayas for India', color: 'bg-blue-500' },
    { text: 'Explain the Revolt of 1857', color: 'bg-red-500' },
  ];

  return (
    <div className={`flex h-screen w-full transition-colors duration-300 ${currentTheme.bg} ${darkMode ? 'text-white' : 'text-black'} overflow-hidden`}>
      
      {/* 1. Left Sidebar */}
      <aside className={`w-64 h-full flex flex-col border-r ${darkMode ? 'border-white/10' : 'border-black/5'} bg-opacity-50 backdrop-blur-xl overflow-y-auto z-20`}>
        <div className="p-6 flex items-center gap-4 group cursor-pointer">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 bg-orange-500 rounded-lg rotate-6 group-hover:rotate-12 transition-transform duration-300"></div>
            <div className="absolute inset-0 bg-[#7E121D] dark:bg-[#B91C1C] rounded-lg -rotate-6 group-hover:-rotate-12 transition-transform duration-300 flex items-center justify-center text-white text-xs font-black shadow-lg">U</div>
          </div>
          <span className="text-xl font-black tracking-tight uppercase">UPSC AI</span>
        </div>

        <div className="flex-1 px-4 py-2">
          {['AI TOOLS', 'PRACTICE'].map((section) => (
            <div key={section} className="mb-6">
              <h3 className="text-xs font-bold text-gray-500 px-4 mb-2 tracking-widest">{section}</h3>
              {sidebarItems.filter(item => item.section === section).map((item) => {
                const isActive = activeSidebar === item.name;
                return (
                  <button
                    key={item.name}
                    onClick={() => setActiveSidebar(item.name)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group mb-1 ${
                      isActive 
                        ? 'bg-orange-600 text-white shadow-lg shadow-orange-600/20' 
                        : 'hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    <item.icon size={20} className={isActive ? 'text-white' : 'text-[#A2411E] dark:text-[#F97316]'} />
                    <span className={`text-sm font-medium ${isActive ? 'text-white' : 'text-[#A2411E] dark:text-[#F97316]'}`}>{item.name}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Bottom Section */}
        <div className="p-4 border-t border-black/5 dark:border-white/10 space-y-4">
          {/* Theme Toggle */}
          <div className="bg-black/5 dark:bg-white/10 p-1 rounded-full flex gap-1">
            <button 
              onClick={() => setDarkMode(false)}
              className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-full text-[10px] font-bold transition-all ${!darkMode ? 'bg-white text-black shadow-sm' : 'text-gray-500'}`}
            >
              <Sun size={14} /> LIGHT
            </button>
            <button 
              onClick={() => setDarkMode(true)}
              className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-full text-[10px] font-bold transition-all ${darkMode ? 'bg-[#1a1a1a] text-white shadow-sm border border-white/10' : 'text-gray-500'}`}
            >
              <Moon size={14} /> DARK
            </button>
          </div>

        </div>
      </aside>

      {/* 2. Main Content */}
      <main className="flex-1 h-full flex flex-col relative overflow-y-auto">
        <div className="absolute inset-0 opacity-20 pointer-events-none">
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-orange-500 rounded-full blur-[120px] -mr-64 -mt-64"></div>
          <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-red-800 rounded-full blur-[120px] -ml-64 -mb-64"></div>
        </div>

        {/* Top Header */}
        <header className="p-8 flex flex-col items-center">
            <div className="flex items-center gap-6 mb-8 group cursor-pointer">
              <div className="relative w-14 h-14">
                <div className="absolute inset-0 bg-orange-500 rounded-2xl rotate-6 group-hover:rotate-12 transition-transform duration-500"></div>
                <div className="absolute inset-0 bg-[#7E121D] dark:bg-[#B91C1C] rounded-2xl -rotate-6 group-hover:-rotate-12 transition-transform duration-500 flex items-center justify-center text-white text-xl font-black shadow-2xl">U</div>
              </div>
              <h1 className="text-5xl font-black tracking-tighter uppercase italic">UPSC AI</h1>
            </div>

            {/* Tab Navigation */}
            <nav className="flex items-center gap-1 p-1 bg-black/10 dark:bg-white/10 backdrop-blur-md rounded-full">
              {[
                { name: 'Questions', icon: BookOpen },
                { name: 'Languages', icon: Globe },
                { name: 'Exams', icon: Ribbon }
              ].map((tab) => {
                const isActive = activeTab === tab.name;
                return (
                  <button
                    key={tab.name}
                    onClick={() => setActiveTab(tab.name)}
                    className={`flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-bold transition-all ${
                      isActive 
                        ? 'bg-[#7E121D] dark:bg-[#B91C1C] text-white shadow-lg' 
                        : 'text-gray-500 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    <tab.icon size={16} />
                    {tab.name}
                  </button>
                );
              })}
            </nav>
        </header>

        {/* Suggestion Cards Grid */}
        <section className="flex-1 w-full max-w-4xl mx-auto px-8 grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
          {suggestionCards.map((card, i) => (
            <div 
              key={i} 
              className={`group ${currentTheme.card} backdrop-blur-md border ${darkMode ? 'border-white/10' : 'border-black/5'} p-6 rounded-3xl hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer relative overflow-hidden`}
            >
              <div className={`absolute top-0 right-0 w-8 h-8 ${card.color} opacity-20 rounded-bl-3xl`}></div>
              <div className={`w-2 h-2 rounded-full ${card.color} mb-4 shadow-lg shadow-${card.color.split('-')[1]}-500/50`}></div>
              <p className="text-lg font-semibold leading-snug">{card.text}</p>
            </div>
          ))}
        </section>

        {/* 3. Bottom Input Bar */}
        <div className="p-8 pb-12 w-full max-w-4xl mx-auto">
          <div className="relative group">
            {/* Gradient Border Implementation */}
            <div className="absolute -inset-[2px] rounded-[40px] bg-gradient-to-r from-green-400 via-yellow-400 to-orange-500 opacity-70 blur-[1px] group-focus-within:opacity-100 transition-opacity"></div>
            
            <div className={`relative px-4 py-3 rounded-[38px] ${darkMode ? 'bg-[#121212]' : 'bg-white'} flex flex-col gap-3 shadow-2xl`}>
              <textarea 
                rows="1"
                placeholder="अपनी UPSC सहायता यहाँ प्राप्त करें..."
                className="w-full bg-transparent border-none focus:ring-0 text-lg py-2 px-4 resize-none placeholder:text-gray-400"
              />
              
              <div className="flex items-center justify-between gap-4 px-2 pb-1">
                <div className="flex items-center gap-2">
                   <button className="flex items-center gap-1.5 px-4 py-2 bg-black/5 dark:bg-white/5 hover:bg-black/10 transition-colors rounded-full text-xs font-bold">
                     English <Globe size={14} className="opacity-50" />
                   </button>
                   <button className="flex items-center gap-1.5 px-4 py-2 bg-black/5 dark:bg-white/5 hover:bg-black/10 transition-colors rounded-full text-xs font-bold">
                     UPSC <Ribbon size={14} className="opacity-50" />
                   </button>
                   <button className="flex items-center gap-1.5 px-4 py-2 bg-black/5 dark:bg-white/5 hover:bg-black/10 transition-colors rounded-full text-xs font-bold text-orange-600 dark:text-orange-400">
                     SEARCH <Sparkles size={14} />
                   </button>
                </div>

                <button className="bg-[#7E121D] dark:bg-[#B91C1C] text-white px-8 py-3 rounded-full flex items-center gap-2 font-black tracking-tight hover:scale-105 transition-transform shadow-lg shadow-red-900/20 uppercase text-xs">
                  Ask Mentor <Send size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
};

export default UPSCMain;
