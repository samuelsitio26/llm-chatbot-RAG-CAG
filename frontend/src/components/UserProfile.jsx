import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  User, Mail, MapPin, Heart, MessageSquare, Lock, 
  ArrowLeft, LogOut, Save, Edit3, RefreshCw, Trash2,
  Camera, Check, X, Home, Shield, Upload, Image
} from 'lucide-react';
import './UserProfile.css';

// Extended emoji options for avatar
const AVATAR_EMOJI_OPTIONS = [
  // People
  '👤', '👨', '👩', '👦', '👧', '🧑', '👨‍💼', '👩‍💼', 
  '👨‍🎓', '👩‍🎓', '🧔', '👱', '👴', '👵', '🤴', '👸',
  '🦸', '🦹', '🧙', '🧝', '🎅', '🤵', '👰', '🥷',
  // More people
  '👨‍🍳', '👩‍🍳', '👨‍🌾', '👩‍🌾', '👨‍🎤', '👩‍🎤', '👨‍💻', '👩‍💻',
  '👨‍🚀', '👩‍🚀', '🧕', '👲', '🤠', '🥸', '🤓', '😎',
  // Animals
  '🐶', '🐱', '🐭', '🐰', '🦊', '🐻', '🐼', '🐨',
  '🦁', '🐯', '🐮', '🐷', '🐸', '🐵', '🦄', '🐲',
  // Nature & Objects
  '🌸', '🌺', '🌻', '🌹', '🌴', '🌈', '⭐', '🌙',
  '🔥', '💎', '🎭', '🎪', '🎨', '🎬', '🎮', '🎯'
];

const CATEGORY_OPTIONS = [
  { id: 'alam', label: 'Wisata Alam', icon: '🏞️', desc: 'Gunung, danau, air terjun' },
  { id: 'budaya', label: 'Wisata Budaya', icon: '🏛️', desc: 'Museum, desa adat, tradisi' },
  { id: 'kuliner', label: 'Kuliner', icon: '🍜', desc: 'Makanan khas, restoran' },
  { id: 'sejarah', label: 'Sejarah', icon: '📜', desc: 'Situs bersejarah, monumen' },
  { id: 'religi', label: 'Wisata Religi', icon: '⛪', desc: 'Gereja, masjid, pura' },
  { id: 'air', label: 'Wisata Air', icon: '🌊', desc: 'Pantai, kolam, water sport' },
  { id: 'petualangan', label: 'Petualangan', icon: '🧗', desc: 'Hiking, camping, rafting' },
  { id: 'fotografi', label: 'Spot Foto', icon: '📸', desc: 'Instagramable, scenic view' }
];

const UserProfile = () => {
  const { user, updateUser, changePassword, getUserChatHistory, clearChatHistory: clearHistory, logout, token } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [avatarTab, setAvatarTab] = useState('emoji'); // 'emoji' or 'upload'
  const [uploadPreview, setUploadPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    bio: '',
    location: '',
    avatar: '👤',
    favorite_categories: []
  });
  
  const [passwordData, setPasswordData] = useState({
    old_password: '',
    new_password: '',
    confirm_password: ''
  });

  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        bio: user.bio || '',
        location: user.location || '',
        avatar: user.avatar || '👤',
        favorite_categories: user.favoriteCategories || user.favorite_categories || []
      });
    }
  }, [user]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadChatHistory();
    }
  }, [activeTab]);

  const loadChatHistory = async () => {
    setLoading(true);
    
    // Try to get from AuthContext (API or localStorage)
    try {
      const history = await getUserChatHistory();
      if (history && history.length > 0) {
        setChatHistory(history);
        setLoading(false);
        return;
      }
    } catch (e) {}
    
    // Fallback to localStorage conversations format
    const allConversations = JSON.parse(localStorage.getItem('toba_conversations') || '{}');
    const history = [];
    
    Object.values(allConversations).forEach(conv => {
      if (conv.messages) {
        conv.messages.forEach(msg => {
          if (msg.role === 'user') {
            const botResponse = conv.messages.find(m => 
              m.role === 'assistant' && new Date(m.timestamp) > new Date(msg.timestamp)
            );
            history.push({
              id: msg.id,
              question: msg.content,
              answer: botResponse?.content || '',
              timestamp: msg.timestamp
            });
          }
        });
      }
    });
    
    // Sort by newest first
    history.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    setChatHistory(history.slice(0, 50));
    setLoading(false);
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCategoryToggle = (categoryId) => {
    setFormData(prev => {
      const categories = prev.favorite_categories || [];
      if (categories.includes(categoryId)) {
        return { ...prev, favorite_categories: categories.filter(c => c !== categoryId) };
      }
      return { ...prev, favorite_categories: [...categories, categoryId] };
    });
  };

  // Handle file selection for avatar upload
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setMessage({ type: 'error', text: 'Format file tidak didukung. Gunakan JPEG, PNG, GIF, atau WebP' });
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      setMessage({ type: 'error', text: 'Ukuran file terlalu besar. Maksimal 2MB' });
      return;
    }

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setUploadPreview(e.target.result);
    };
    reader.readAsDataURL(file);
  };

  // Upload avatar image
  const handleAvatarUpload = async () => {
    if (!uploadPreview) return;

    setUploading(true);
    try {
      const response = await fetch('/api/user/avatar/base64', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ avatar: uploadPreview })
      });

      const data = await response.json();

      if (data.success) {
        setFormData(prev => ({ ...prev, avatar: data.avatar }));
        setMessage({ type: 'success', text: 'Avatar berhasil diupload!' });
        setShowAvatarPicker(false);
        setUploadPreview(null);
        
        // Update user context
        await updateUser({ avatar: data.avatar });
      } else {
        setMessage({ type: 'error', text: data.detail || 'Gagal upload avatar' });
      }
    } catch (error) {
      console.error('Avatar upload error:', error);
      setMessage({ type: 'error', text: 'Gagal upload avatar' });
    }
    setUploading(false);
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  // Select emoji as avatar
  const handleEmojiSelect = async (emoji) => {
    setFormData(prev => ({ ...prev, avatar: emoji }));
    setShowAvatarPicker(false);

    // Auto-save emoji avatar to backend (same as image upload)
    try {
      const result = await updateUser({ avatar: emoji });
      if (result.success) {
        setMessage({ type: 'success', text: 'Avatar berhasil diperbarui!' });
      } else {
        setMessage({ type: 'error', text: result.message || 'Gagal menyimpan avatar' });
      }
    } catch (error) {
      console.error('Emoji avatar save error:', error);
      setMessage({ type: 'error', text: 'Gagal menyimpan avatar' });
    }
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  // Check if avatar is an image URL
  const isImageAvatar = (avatar) => {
    return avatar && (
      avatar.startsWith('/api/avatars/') || 
      avatar.startsWith('data:image') || 
      avatar.startsWith('http://') ||
      avatar.startsWith('https://')
    );
  };

  const handleSaveProfile = async () => {
    setLoading(true);
    
    try {
      // Update via AuthContext (handles both API and localStorage)
      const result = await updateUser({
        name: formData.name,
        avatar: formData.avatar,
        bio: formData.bio,
        location: formData.location,
        favorite_categories: formData.favorite_categories
      });
      
      if (result.success) {
        setMessage({ type: 'success', text: 'Profil berhasil diperbarui!' });
        setIsEditing(false);
      } else {
        setMessage({ type: 'error', text: result.message || 'Gagal menyimpan profil' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Gagal menyimpan profil' });
    }
    
    setLoading(false);
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    
    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ type: 'error', text: 'Konfirmasi password tidak cocok' });
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
      return;
    }
    
    if (passwordData.new_password.length < 6) {
      setMessage({ type: 'error', text: 'Password minimal 6 karakter' });
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
      return;
    }
    
    setLoading(true);
    
    try {
      const result = await changePassword(passwordData.old_password, passwordData.new_password);
      
      if (result.success) {
        setMessage({ type: 'success', text: result.message || 'Password berhasil diubah!' });
        setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
        
        // If backend logout happened, redirect to login
        if (result.message?.includes('login kembali')) {
          setTimeout(() => navigate('/login'), 2000);
        }
      } else {
        setMessage({ type: 'error', text: result.message || 'Gagal mengubah password' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Terjadi kesalahan' });
    }
    
    setLoading(false);
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('id-ID', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const handleClearHistory = async () => {
    if (window.confirm('Hapus semua riwayat chat? Tindakan ini tidak dapat dibatalkan.')) {
      setLoading(true);
      await clearHistory();
      localStorage.removeItem('toba_conversations');
      setChatHistory([]);
      setLoading(false);
      setMessage({ type: 'success', text: 'Riwayat chat berhasil dihapus' });
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
    }
  };

  if (!user) {
    navigate('/login');
    return null;
  }

  return (
    <div className="user-profile-page">
      {/* Header */}
      <header className="up-header">
        <div className="up-header-left">
          <button className="up-back-btn" onClick={() => navigate('/')}>
            <ArrowLeft size={20} />
            <span>Kembali</span>
          </button>
        </div>
        <h1 className="up-title">
          <User size={24} />
          Profil Saya
        </h1>
        <div className="up-header-right">
          {(user.role === 'admin' || user.role === 'operator') && (
            <Link to="/admin" className="up-admin-btn">
              <Shield size={18} />
              <span>Dashboard</span>
            </Link>
          )}
          <button className="up-logout-btn" onClick={handleLogout}>
            <LogOut size={18} />
            <span>Keluar</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="up-main">
        {/* Profile Card */}
        <div className="up-profile-card">
          {/* Avatar Section */}
          <div className="up-avatar-section">
            <div 
              className="up-avatar-container editable"
              onClick={() => setShowAvatarPicker(true)}
              title="Klik untuk ganti avatar"
            >
              {isImageAvatar(formData.avatar) ? (
                <img 
                  src={formData.avatar} 
                  alt="Avatar" 
                  className="up-avatar-img"
                  crossOrigin="anonymous"
                  referrerPolicy="no-referrer"
                  onError={(e) => e.target.style.display = 'none'}
                />
              ) : (
                <span className="up-avatar">{formData.avatar}</span>
              )}
              <div className="up-avatar-overlay">
                <Camera size={24} />
                <span className="up-avatar-hint">Ganti</span>
              </div>
            </div>
            
            {/* Avatar Picker Modal - Enhanced */}
            {showAvatarPicker && (
              <div className="up-modal-overlay" onClick={() => { setShowAvatarPicker(false); setUploadPreview(null); }}>
                <div className="up-avatar-picker up-avatar-picker--enhanced" onClick={e => e.stopPropagation()}>
                  <div className="up-picker-header">
                    <h3>Pilih Avatar</h3>
                    <button onClick={() => { setShowAvatarPicker(false); setUploadPreview(null); }}>
                      <X size={20} />
                    </button>
                  </div>
                  
                  {/* Tabs: Emoji / Upload */}
                  <div className="up-avatar-tabs">
                    <button 
                      className={`up-avatar-tab ${avatarTab === 'emoji' ? 'active' : ''}`}
                      onClick={() => setAvatarTab('emoji')}
                    >
                      😊 Emoji
                    </button>
                    <button 
                      className={`up-avatar-tab ${avatarTab === 'upload' ? 'active' : ''}`}
                      onClick={() => setAvatarTab('upload')}
                    >
                      <Upload size={16} /> Upload Foto
                    </button>
                  </div>
                  
                  {/* Emoji Grid */}
                  {avatarTab === 'emoji' && (
                    <div className="up-avatar-grid">
                      {AVATAR_EMOJI_OPTIONS.map(emoji => (
                        <button
                          key={emoji}
                          className={`up-avatar-option ${formData.avatar === emoji ? 'selected' : ''}`}
                          onClick={() => handleEmojiSelect(emoji)}
                        >
                          {emoji}
                          {formData.avatar === emoji && (
                            <span className="up-avatar-check"><Check size={12} /></span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {/* Upload Section */}
                  {avatarTab === 'upload' && (
                    <div className="up-avatar-upload">
                      {/* Hidden file input */}
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        accept="image/jpeg,image/png,image/gif,image/webp"
                        style={{ display: 'none' }}
                      />
                      
                      {/* Preview or Upload Button */}
                      {uploadPreview ? (
                        <div className="up-upload-preview">
                          <img src={uploadPreview} alt="Preview" />
                          <div className="up-upload-actions">
                            <button 
                              className="up-upload-btn up-upload-btn--confirm"
                              onClick={handleAvatarUpload}
                              disabled={uploading}
                            >
                              {uploading ? (
                                <>
                                  <RefreshCw size={16} className="spinning" />
                                  Mengupload...
                                </>
                              ) : (
                                <>
                                  <Check size={16} />
                                  Gunakan Foto Ini
                                </>
                              )}
                            </button>
                            <button 
                              className="up-upload-btn up-upload-btn--cancel"
                              onClick={() => setUploadPreview(null)}
                            >
                              <X size={16} />
                              Batal
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div 
                          className="up-upload-dropzone"
                          onClick={() => fileInputRef.current?.click()}
                        >
                          <Image size={48} />
                          <p>Klik untuk upload foto</p>
                          <span>JPEG, PNG, GIF, WebP (Max 2MB)</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <div className="up-user-info">
              <h2 className="up-user-name">{user.name}</h2>
              <span className="up-username">@{user.username}</span>
              <span className={`up-role-badge role-${user.role}`}>
                {user.role === 'admin' ? '👨‍💼 Administrator' : 
                 user.role === 'operator' ? '👨‍🔧 Operator' : '👤 User'}
              </span>
            </div>
          </div>

          {/* Stats */}
          <div className="up-stats">
            <div className="up-stat-item">
              <span className="up-stat-value">{chatHistory.length}</span>
              <span className="up-stat-label">Pertanyaan</span>
            </div>
            <div className="up-stat-item">
              <span className="up-stat-value">{formData.favorite_categories?.length || 0}</span>
              <span className="up-stat-label">Kategori Favorit</span>
            </div>
            <div className="up-stat-item">
              <span className="up-stat-value">{formatDate(user.createdAt).split(',')[0]}</span>
              <span className="up-stat-label">Bergabung</span>
            </div>
          </div>
        </div>

        {/* Message Alert */}
        {message.text && (
          <div className={`up-alert up-alert-${message.type}`}>
            {message.type === 'success' ? <Check size={18} /> : <X size={18} />}
            {message.text}
          </div>
        )}

        {/* Tabs */}
        <div className="up-tabs">
          <button 
            className={`up-tab ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            <User size={18} />
            <span>Profil</span>
          </button>
          <button 
            className={`up-tab ${activeTab === 'preferences' ? 'active' : ''}`}
            onClick={() => setActiveTab('preferences')}
          >
            <Heart size={18} />
            <span>Preferensi</span>
          </button>
          <button 
            className={`up-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <MessageSquare size={18} />
            <span>Riwayat</span>
          </button>
          <button 
            className={`up-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <Lock size={18} />
            <span>Keamanan</span>
          </button>
        </div>

        {/* Tab Content */}
        <div className="up-content">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="up-section">
              <div className="up-section-header">
                <h3>Informasi Profil</h3>
                {!isEditing ? (
                  <button className="up-edit-btn" onClick={() => setIsEditing(true)}>
                    <Edit3 size={16} />
                    Edit
                  </button>
                ) : (
                  <div className="up-edit-actions">
                    <button className="up-cancel-btn" onClick={() => {
                      setIsEditing(false);
                      setFormData({
                        name: user.name || '',
                        email: user.email || '',
                        bio: user.bio || '',
                        location: user.location || '',
                        avatar: user.avatar || '👤',
                        favorite_categories: user.favorite_categories || []
                      });
                    }}>
                      <X size={16} />
                      Batal
                    </button>
                    <button className="up-save-btn" onClick={handleSaveProfile} disabled={loading}>
                      <Save size={16} />
                      {loading ? 'Menyimpan...' : 'Simpan'}
                    </button>
                  </div>
                )}
              </div>

              <div className="up-form">
                <div className="up-form-row">
                  <div className="up-form-group">
                    <label><User size={16} /> Nama Lengkap</label>
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={handleInputChange}
                      disabled={!isEditing}
                      placeholder="Masukkan nama lengkap"
                    />
                  </div>
                  <div className="up-form-group">
                    <label><Mail size={16} /> Email</label>
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      disabled={!isEditing}
                      placeholder="Masukkan email"
                    />
                  </div>
                </div>

                <div className="up-form-group">
                  <label><MapPin size={16} /> Lokasi</label>
                  <input
                    type="text"
                    name="location"
                    value={formData.location}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    placeholder="Kota/Daerah tempat tinggal"
                  />
                </div>

                <div className="up-form-group">
                  <label>📝 Bio</label>
                  <textarea
                    name="bio"
                    value={formData.bio}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    placeholder="Ceritakan sedikit tentang diri Anda..."
                    rows={4}
                  />
                </div>

                <div className="up-form-group">
                  <label>👤 Username</label>
                  <input
                    type="text"
                    value={user.username}
                    disabled
                    className="up-readonly"
                  />
                  <small>Username tidak dapat diubah</small>
                </div>
              </div>
            </div>
          )}

          {/* Preferences Tab */}
          {activeTab === 'preferences' && (
            <div className="up-section">
              <div className="up-section-header">
                <h3>🎯 Kategori Wisata Favorit</h3>
              </div>
              <p className="up-section-desc">
                Pilih kategori wisata yang Anda sukai. Ini akan membantu kami memberikan rekomendasi yang lebih personal sesuai minat Anda.
              </p>

              <div className="up-category-grid">
                {CATEGORY_OPTIONS.map(category => (
                  <button
                    key={category.id}
                    className={`up-category-card ${formData.favorite_categories.includes(category.id) ? 'selected' : ''}`}
                    onClick={() => handleCategoryToggle(category.id)}
                  >
                    <span className="up-cat-icon">{category.icon}</span>
                    <span className="up-cat-name">{category.label}</span>
                    <span className="up-cat-desc">{category.desc}</span>
                    {formData.favorite_categories.includes(category.id) && (
                      <span className="up-cat-check"><Check size={16} /></span>
                    )}
                  </button>
                ))}
              </div>

              <div className="up-form-actions">
                <button className="up-save-btn" onClick={handleSaveProfile} disabled={loading}>
                  <Save size={18} />
                  {loading ? 'Menyimpan...' : 'Simpan Preferensi'}
                </button>
              </div>
            </div>
          )}

          {/* History Tab */}
          {activeTab === 'history' && (
            <div className="up-section">
              <div className="up-section-header">
                <h3>💬 Riwayat Percakapan</h3>
                <div className="up-history-actions">
                  <button className="up-refresh-btn" onClick={loadChatHistory} disabled={loading}>
                    <RefreshCw size={16} className={loading ? 'spin' : ''} />
                    Refresh
                  </button>
                  {chatHistory.length > 0 && (
                    <button className="up-clear-btn" onClick={handleClearHistory} disabled={loading}>
                      <Trash2 size={16} />
                      Hapus Semua
                    </button>
                  )}
                </div>
              </div>

              {chatHistory.length === 0 ? (
                <div className="up-empty-state">
                  <MessageSquare size={48} />
                  <h4>Belum Ada Riwayat</h4>
                  <p>Anda belum memiliki riwayat percakapan. Mulai chat dengan bot untuk mendapatkan rekomendasi wisata!</p>
                  <button className="up-start-chat-btn" onClick={() => navigate('/')}>
                    <Home size={18} />
                    Mulai Chat Sekarang
                  </button>
                </div>
              ) : (
                <div className="up-history-list">
                  {chatHistory.map((item, index) => (
                    <div key={item.id || index} className="up-history-item">
                      <div className="up-history-question">
                        <span className="up-history-label">
                          <User size={14} /> Pertanyaan Anda
                        </span>
                        <p>{item.question || item.message}</p>
                      </div>
                      {(item.answer || item.response) && (
                        <div className="up-history-answer">
                          <span className="up-history-label">
                            🤖 Jawaban Bot
                          </span>
                          <p>{(item.answer || item.response).length > 200 
                            ? `${(item.answer || item.response).substring(0, 200)}...` 
                            : (item.answer || item.response)}</p>
                        </div>
                      )}
                      <div className="up-history-time">
                        {formatDate(item.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="up-section">
              <div className="up-section-header">
                <h3>🔒 Keamanan Akun</h3>
              </div>

              <div className="up-security-card">
                <h4>Ubah Password</h4>
                <form onSubmit={handleChangePassword} className="up-password-form">
                  <div className="up-form-group">
                    <label>Password Lama</label>
                    <input
                      type="password"
                      value={passwordData.old_password}
                      onChange={(e) => setPasswordData(prev => ({ ...prev, old_password: e.target.value }))}
                      placeholder="Masukkan password lama"
                      required
                    />
                  </div>
                  <div className="up-form-group">
                    <label>Password Baru</label>
                    <input
                      type="password"
                      value={passwordData.new_password}
                      onChange={(e) => setPasswordData(prev => ({ ...prev, new_password: e.target.value }))}
                      placeholder="Minimal 6 karakter"
                      required
                      minLength={6}
                    />
                  </div>
                  <div className="up-form-group">
                    <label>Konfirmasi Password Baru</label>
                    <input
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e) => setPasswordData(prev => ({ ...prev, confirm_password: e.target.value }))}
                      placeholder="Ulangi password baru"
                      required
                    />
                  </div>
                  <button type="submit" className="up-change-pwd-btn">
                    <Lock size={18} />
                    Ubah Password
                  </button>
                </form>
              </div>

              <div className="up-danger-zone">
                <h4>⚠️ Zona Berbahaya</h4>
                <p>Menghapus akun akan menghapus semua data Anda secara permanen. Tindakan ini tidak dapat dibatalkan.</p>
                <button className="up-delete-btn" disabled>
                  <Trash2 size={18} />
                  Hapus Akun (Coming Soon)
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default UserProfile;
