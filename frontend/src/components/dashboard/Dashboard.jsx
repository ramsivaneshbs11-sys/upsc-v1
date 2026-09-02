import React from 'react';
import { Search, ChevronRight, GraduationCap, Globe2, BookOpen } from 'lucide-react';
import { dummyQuestions } from '../../data/dummyData';
import { useApp } from '../../context/AppContext';
import { motion } from 'framer-motion';

const Dashboard = () => {
  const { setActiveTab, setChatInput } = useApp();

  const handleCardClick = (question) => {
    setChatInput(question);
    setActiveTab('Ask UPSC AI');
  };

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const item = {
    hidden: { y: 20, opacity: 0 },
    show: { y: 0, opacity: 1 }
  };

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto pb-32 md:pb-8">
      {/* Header Tabs */}
      <div className="flex items-center gap-8 mb-12 border-b border-upsc-navy/30">
        {['Questions', 'Languages', 'Exams'].map((tab, idx) => (
          <button 
            key={tab}
            className={`pb-4 px-2 text-sm font-semibold transition-all relative ${idx === 0 ? 'text-upsc-gold' : 'text-gray-500 hover:text-gray-300'}`}
          >
            {tab}
            {idx === 0 && <span className="absolute bottom-0 left-0 w-full h-1 bg-upsc-gold rounded-full" />}
          </button>
        ))}
      </div>

      <div className="mb-12">
        <h2 className="text-3xl font-extrabold text-[var(--text-main)] mb-2">Welcome Back, Aspirant!</h2>
        <p className="text-[var(--text-muted)] max-w-2xl">Your AI-powered mentor is ready to help you crack UPSC. Start by asking a doubt or picking a curated topic below.</p>
      </div>

      {/* Stats / Quick Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {[
          { label: 'Exam Mode', value: 'UPSC CSE (2026)', icon: GraduationCap, color: 'bg-blue-500/10 text-blue-400' },
          { label: 'Language', value: 'English / Hindi', icon: Globe2, color: 'bg-green-500/10 text-green-400' },
          { label: 'Course Progress', value: '42% Completed', icon: BookOpen, color: 'bg-purple-500/10 text-purple-400' },
        ].map((stat, i) => (
          <div key={i} className="bg-[var(--bg-card)] border border-upsc-navy/10 p-6 flex items-center gap-4 rounded-3xl shadow-lg transition-colors">
            <div className={`p-3 rounded-2xl ${stat.color}`}>
              <stat.icon size={24} />
            </div>
            <div>
              <p className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">{stat.label}</p>
              <p className="text-lg font-bold text-[var(--text-main)]">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Grid */}
      <h3 className="text-xl font-bold text-upsc-navy mb-6 flex items-center gap-2">
        <ChevronRight className="text-upsc-gold" /> Suggested for you
      </h3>
      
      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6"
      >
        {dummyQuestions.map((q) => (
          <motion.div 
            key={q.id}
            variants={item}
            onClick={() => handleCardClick(q.title)}
            className="group cursor-pointer bg-[var(--bg-card)] border border-[var(--border-color)] p-8 border-l-8 hover:translate-x-1 rounded-3xl shadow-lg transition-all"
            style={{ 
              borderLeftColor: q.color === 'orange' ? '#D4AF37' : q.color === 'blue' ? '#3b82f6' : '#10b981' 
            }}
          >
            <div className="flex justify-between items-start">
              <div>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest mb-3 inline-block 
                  ${q.color === 'orange' ? 'bg-upsc-gold/10 text-upsc-gold' : 
                    q.color === 'blue' ? 'bg-blue-500/10 text-blue-400' : 'bg-green-500/10 text-green-400'}`}
                >
                  {q.category}
                </span>
                <h4 className="text-lg font-bold text-upsc-navy group-hover:text-upsc-gold transition-colors leading-tight">
                  {q.title}
                </h4>
              </div>
              <div className="p-2 bg-gray-100 text-upsc-navy rounded-full group-hover:bg-upsc-gold group-hover:text-white transition-all transform group-hover:rotate-45">
                <ChevronRight size={20} />
              </div>
            </div>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
};

export default Dashboard;
