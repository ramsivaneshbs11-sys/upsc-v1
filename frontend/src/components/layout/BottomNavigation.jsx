import React from 'react';
import { MessageSquare, CheckSquare, Newspaper, BookMarked, LayoutDashboard, Upload, BookOpen, HardDrive } from 'lucide-react';
import { useApp } from '../../context/AppContext';

const STUDENT_TABS = [
  { name: 'Ask UPSC AI',    icon: MessageSquare, label: 'Chat' },
  { name: 'MCQ Practice AI', icon: CheckSquare,   label: 'MCQ'  },
  { name: 'Daily News',      icon: Newspaper,     label: 'News' },
  { name: 'Quick Notes',     icon: BookMarked,    label: 'Notes'},
];

const ADMIN_TABS = [
  { name: 'Admin Dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { name: 'Admin Panel',      icon: Upload,          label: 'Ingest'    },
  { name: 'Admin Panel',      icon: BookOpen,        label: 'Syllabus'  },
  { name: 'Admin Panel',      icon: HardDrive,       label: 'Cache'     },
];

const BottomNavigation = () => {
  const { activeTab, setActiveTab, userRole } = useApp();
  const isAdmin = userRole === 'admin';
  const tabs = isAdmin ? ADMIN_TABS : STUDENT_TABS;

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-lg border-t border-gray-100 px-4 py-3 flex justify-between items-center z-[100] md:hidden rounded-t-[32px] shadow-[0_-10px_25px_-5px_rgba(0,0,0,0.05)]">
      {tabs.map((tab, i) => {
        const isActive = activeTab === tab.name;
        const activeColor = isAdmin ? 'from-upsc-maroon to-upsc-maroon/80' : 'from-upsc-navy to-upsc-maroon';
        const activeText  = isAdmin ? 'text-upsc-maroon' : 'text-upsc-navy';
        return (
          <button
            key={`${tab.name}-${i}`}
            onClick={() => setActiveTab(tab.name)}
            className={`flex flex-col items-center gap-1.5 transition-all duration-300 ${
              isActive ? 'scale-110' : 'opacity-60 grayscale'
            }`}
          >
            <div className={`p-2 rounded-2xl transition-all duration-300 ${
              isActive
                ? `bg-gradient-to-br ${activeColor} text-white shadow-lg`
                : 'text-slate-600'
            }`}>
              <tab.icon size={20} strokeWidth={isActive ? 2.5 : 2} />
            </div>
            <span className={`text-[10px] font-bold uppercase tracking-widest ${
              isActive ? activeText : 'text-slate-500'
            }`}>
              {tab.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
};

export default BottomNavigation;
