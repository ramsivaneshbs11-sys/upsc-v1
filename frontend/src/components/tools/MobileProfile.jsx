import React from 'react';
import { useApp } from '../../context/AppContext';
import { LogOut, ShieldCheck, Phone, Mail, ChevronRight, User } from 'lucide-react';
import { motion } from 'framer-motion';

const MobileProfile = () => {
  const { user, logout } = useApp();

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-[80vh] px-8 text-center">
        <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mb-6">
          <User size={40} className="text-slate-300" />
        </div>
        <h2 className="text-2xl font-bold text-upsc-navy mb-2">Not Logged In</h2>
        <p className="text-slate-500 mb-8">Please login to view your profile and sync your progress.</p>
      </div>
    );
  }

  return (
    <div className="p-6 pb-32">
      <div className="flex flex-col items-center mb-10">
        <motion.div 
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="relative mb-4"
        >
          <div className="w-28 h-28 rounded-full bg-gradient-to-br from-upsc-navy to-upsc-maroon p-1 shadow-2xl">
            <div className="w-full h-full rounded-full bg-white flex items-center justify-center text-4xl font-black text-upsc-navy">
              {user.name?.charAt(0).toUpperCase()}
            </div>
          </div>
          <div className="absolute bottom-1 right-1 bg-green-500 w-6 h-6 rounded-full border-4 border-white"></div>
        </motion.div>
        
        <h2 className="text-2xl font-black text-upsc-navy mb-1">{user.name}</h2>
        <div className="flex items-center gap-2 px-4 py-1.5 bg-upsc-gold/10 rounded-full">
          <ShieldCheck size={14} className="text-upsc-gold" />
          <span className="text-[10px] font-bold text-upsc-gold uppercase tracking-[0.2em]">{user.plan || 'PRO'} PLAN</span>
        </div>
      </div>

      <div className="space-y-4 mb-10">
        <div className="bg-white border border-slate-100 rounded-[24px] p-5 shadow-sm">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-500">
              <Phone size={18} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Phone Number</p>
              <p className="text-sm font-bold text-upsc-navy">{user.phone || '+91 9999999999'}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500">
              <Mail size={18} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Email Address</p>
              <p className="text-sm font-bold text-upsc-navy">{user.email || 'aspirant@upscai.com'}</p>
            </div>
          </div>
        </div>

        <button 
          onClick={() => {
            logout();
            window.location.href = '/';
          }}
          className="w-full bg-red-50 hover:bg-red-100 text-red-600 font-bold py-4 rounded-[24px] flex items-center justify-center gap-2 transition-all active:scale-95"
        >
          <LogOut size={20} /> Logout Account
        </button>
      </div>

      <p className="text-center text-[10px] text-slate-300 font-bold uppercase tracking-[0.3em]">
        UPSC AI Platform v2.0
      </p>
    </div>
  );
};

export default MobileProfile;
