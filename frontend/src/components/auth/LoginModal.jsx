import React from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Logo from '../Logo';

const LoginModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-[400px] bg-white rounded-[32px] p-8 border border-gray-100 shadow-2xl relative mx-4"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <Logo showText={false} className="h-10 w-auto" />
                <div className="flex flex-col">
                  <span className="text-xl font-bold tracking-tight text-upsc-navy">SELVA'S</span>
                  <span className="text-[10px] uppercase tracking-widest text-upsc-gold font-bold">IAS ACADEMY</span>
                </div>
              </div>
              <button 
                onClick={onClose}
                className="text-gray-400 hover:text-upsc-navy transition-colors p-2"
              >
                <X size={24} />
              </button>
            </div>

            {/* Phone Input Area */}
            <div className="mb-6">
              <label className="block text-[var(--text-main)] text-[15px] font-semibold mb-3">
                Enter the phone number
              </label>
              <input 
                type="text" 
                placeholder="+91 9999999999" 
                className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-5 py-4 text-[var(--text-main)] text-lg focus:outline-none focus:border-upsc-navy/30 transition-colors placeholder:text-gray-400 font-medium tracking-wide"
              />
            </div>

            {/* Send OTP Button */}
            <button className="w-full bg-[#2563EB] hover:bg-blue-600 text-white font-bold py-4 rounded-2xl transition-colors mb-8 text-lg shadow-lg shadow-blue-900/20">
              Send OTP
            </button>

            {/* Divider */}
            <div className="flex items-center gap-4 mb-8">
              <div className="h-[1px] flex-1 bg-gray-100"></div>
              <span className="text-gray-400 text-xs font-bold uppercase tracking-wider">OR</span>
              <div className="h-[1px] flex-1 bg-gray-100"></div>
            </div>

            {/* Google Sign In */}
            <button className="w-full bg-gray-50 hover:bg-gray-100 text-[var(--text-main)] font-bold py-4 rounded-2xl transition-colors flex items-center justify-center gap-3 mb-10 border border-gray-100">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25C22.56 11.47 22.49 10.72 22.36 10H12V14.26H17.92C17.66 15.63 16.88 16.81 15.71 17.59V20.34H19.28C21.36 18.42 22.56 15.6 22.56 12.25Z" fill="#4285F4"/>
                <path d="M12 23C14.97 23 17.46 22.02 19.28 20.34L15.71 17.59C14.73 18.25 13.48 18.64 12 18.64C9.13 18.64 6.7 16.7 5.82 14.11H2.14V16.96C3.96 20.58 7.68 23 12 23Z" fill="#34A853"/>
                <path d="M5.82 14.11C5.6 13.45 5.47 12.74 5.47 12C5.47 11.26 5.6 10.55 5.82 9.89V7.04H2.14C1.39 8.53 0.96 10.21 0.96 12C0.96 13.79 1.39 15.47 2.14 16.96L5.82 14.11Z" fill="#FBBC05"/>
                <path d="M12 5.38C13.62 5.38 15.06 5.93 16.2 7.02L19.36 3.86C17.45 2.08 14.97 1 12 1C7.68 1 3.96 3.42 2.14 7.04L5.82 9.89C6.7 7.3 9.13 5.38 12 5.38Z" fill="#EA4335"/>
              </svg>
              Sign in with Google
            </button>

            {/* Footer Terms */}
            <p className="text-center text-gray-400 text-sm leading-relaxed max-w-[280px] mx-auto font-medium">
              By continuing, you agree to our <a href="#" className="text-[#3B82F6] hover:underline">Terms</a> and <a href="#" className="text-[#3B82F6] hover:underline">Privacy Policy</a>
            </p>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default LoginModal;
