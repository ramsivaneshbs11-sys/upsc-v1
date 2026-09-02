import React from 'react';
import logoImg from '../assets/logo/split/Selva\'s_IAS_Academy_Logo.png';

const Logo = ({ className = "h-16 w-auto", showText = true }) => {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <img 
        src={logoImg} 
        alt="Selva's IAS Academy" 
        className="h-full w-auto object-contain shrink-0"
      />
      {showText && (
        <div className="flex flex-col shrink-0 min-w-0">
          <div className="flex items-center gap-1 flex-wrap">
            <span style={{ color: '#2b3990', fontSize: '0.85rem', fontWeight: '900', lineHeight: '1.1', fontFamily: 'Outfit, sans-serif' }}>SELVA'S</span>
            <span style={{ color: '#8b0000', fontSize: '0.85rem', fontWeight: '900', lineHeight: '1.1', fontFamily: 'Outfit, sans-serif' }}>IAS</span>
            <span style={{ color: '#2b3990', fontSize: '0.85rem', fontWeight: '900', lineHeight: '1.1', fontFamily: 'Outfit, sans-serif' }}>ACADEMY</span>
          </div>
          <div style={{ color: '#8b0000', fontSize: '0.5rem', fontWeight: '800', letterSpacing: '0.02em', marginTop: '1px', fontFamily: 'Outfit, sans-serif', whiteSpace: 'nowrap' }}>
            DISCOVER PATH TO UPSC
          </div>
          <div style={{ color: '#8b0000', fontSize: '0.42rem', fontWeight: '700', alignSelf: 'flex-end', opacity: 0.9, marginTop: '-1px', fontFamily: 'Outfit, sans-serif' }}>
            IAS, IPS, IFS...
          </div>
        </div>
      )}
    </div>
  );
};

export default Logo;
