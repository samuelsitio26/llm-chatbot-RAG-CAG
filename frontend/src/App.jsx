import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import { Send, TrendingUp, Server, Database, ThumbsUp, ThumbsDown, RefreshCw, Plus, MapPin, LogIn, Settings, User, LogOut, ChevronLeft, ChevronRight, ChevronDown, UserCircle, Menu, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import MapView from './MapView';
import 'leaflet/dist/leaflet.css';
import { useAuth } from './context/AuthContext';

// ✅ Use relative URL - Vite will proxy to backend
const API_BASE_URL = '/api';

console.log('🔗 API URL:', API_BASE_URL);

function App() {
  const { user, isAuthenticated, logout, updateUserStats, isAdmin } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [showStats, setShowStats] = useState(false);
  const [sessionId] = useState(`session_${Date.now()}`);
  const [conversations, setConversations] = useState({});
  const [activeConvId, setActiveConvId] = useState(null);
  
  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // User menu dropdown
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);
  
  // Map state
  const [locations, setLocations] = useState([]);
  const [showMap, setShowMap] = useState(false);
  const [showMapInChat, setShowMapInChat] = useState(false);
  const [mapFilter, setMapFilter] = useState(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchStatus();
    fetchLocations(); // Load map locations on mount
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch map locations
  const fetchLocations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/locations`);
      if (response.data.locations) {
        setLocations(response.data.locations);
        console.log(`📍 Loaded ${response.data.locations.length} map locations`);
      }
    } catch (error) {
      console.error('Error fetching locations:', error);
    }
  };

  // Detect location mentions in messages to show map
  const detectLocationMention = (text) => {
    const locationKeywords = [
      'pantai', 'pulau', 'danau', 'parapat', 'samosir', 'tuktuk', 'tomok',
      'ambarita', 'simanindo', 'balige', 'pangururan', 'sipiso', 'tongging',
      'air terjun', 'bukit', 'gunung', 'hotel', 'resort', 'penginapan'
    ];
    const lowerText = text.toLowerCase();
    return locationKeywords.some(kw => lowerText.includes(kw));
  };

  // Load conversations from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('toba_conversations_v1');
      if (saved) {
        const parsed = JSON.parse(saved);
        setConversations(parsed);
        const ids = Object.keys(parsed);
        if (ids.length > 0) setActiveConvId(ids[0]);
      } else {
        // create default conversation
        const id = `conv_${Date.now()}`;
        const init = {
          [id]: { id, title: 'General', messages: [] }
        };
        setConversations(init);
        setActiveConvId(id);
      }
    } catch (e) {
      console.error('Error loading conversations', e);
    }
  }, []);

  useEffect(() => {
    if (!activeConvId) return;
    // sync messages view with active conversation
    const conv = conversations[activeConvId];
    if (conv) setMessages(conv.messages || []);
  }, [activeConvId, conversations]);

  const persistConversations = (next) => {
    try {
      localStorage.setItem('toba_conversations_v1', JSON.stringify(next));
    } catch (e) {
      console.error('Error saving conversations', e);
    }
  };

  // Fetch system status
  const fetchStatus = async () => {
    try {
      console.log('📡 Fetching status from:', `${API_BASE_URL}/status`);
      const response = await axios.get(`${API_BASE_URL}/status`, {
        timeout: 5000 // 5 second timeout
      });
      setSystemStatus(response.data);
    } catch (error) {
      console.error('❌ Error fetching status:', error.message);
      setSystemStatus(prev => ({ ...prev, status: 'error' }));
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching stats:', error);
      return null;
    }
  };

  // Handle Shift+Enter for new line, Enter to submit
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: `m_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    // update conversation
    if (activeConvId) {
      const next = { ...conversations };
      next[activeConvId] = { ...next[activeConvId], messages: newMessages };
      setConversations(next);
      persistConversations(next);
    }

    setInput('');
    setIsLoading(true);

    try {
      console.log('📤 Sending message:', userMessage.content);
      
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        query: userMessage.content,
        session_id: sessionId,
        use_cache: true,
        k: 5,
        max_new_tokens: 2048,
        temperature: 0.7
      }, {
        timeout: 120000 // 2 minute timeout for generation
      });

      console.log('✅ Response:', response.data);

      const assistantMessage = {
        id: `m_${Date.now()+1}`,
        role: 'assistant',
        content: response.data.response,
        metadata: response.data.metadata || {},
        source: response.data.source,
        cache_used: response.data.cache_used,
        response_time: response.data.response_time,
        timestamp: new Date().toISOString()
      };

      const updatedMessages = [...newMessages, assistantMessage];
      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }

      // Update user stats for activity tracking
      if (isAuthenticated && updateUserStats) {
        updateUserStats('chat', { query: userMessage.content });
      }
    } catch (error) {
      console.error('❌ Error:', error);
      
      const errorMessage = {
        id: `m_${Date.now()+2}`,
        role: 'assistant',
        content: `Maaf, terjadi kesalahan: ${error.response?.data?.detail || error.message || 'Network error'}. Pastikan backend server berjalan di port 8000.`,
        metadata: {},
        source: 'error',
        timestamp: new Date().toISOString()
      };

      const updatedMessages = [...newMessages, errorMessage];
      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Create new conversation
  const createConversation = (title = 'New Conversation') => {
    const id = `conv_${Date.now()}`;
    const next = { ...conversations, [id]: { id, title, messages: [] } };
    setConversations(next);
    setActiveConvId(id);
    persistConversations(next);
  };

  const selectConversation = (id) => {
    setActiveConvId(id);
  };

  const renameConversation = (id) => {
    const name = window.prompt('Nama percakapan (mis. Parapat, Tuk-Tuk, Tomok):', conversations[id].title || 'Conversation');
    if (!name) return;
    const next = { ...conversations };
    next[id] = { ...next[id], title: name };
    setConversations(next);
    persistConversations(next);
  };

  const deleteConversation = (id) => {
    if (!window.confirm('Hapus percakapan ini?')) return;
    const next = { ...conversations };
    delete next[id];
    setConversations(next);
    persistConversations(next);
    const ids = Object.keys(next);
    setActiveConvId(ids.length > 0 ? ids[0] : null);
  };

  // Feedback (thumbs up/down)
  const handleFeedback = async (messageId, rating) => {
    try {
      await axios.post(`${API_BASE_URL}/feedback`, {
        session_id: activeConvId || sessionId,
        message_id: messageId,
        rating
      });

      // update local message metadata
      const updated = messages.map(m => m.id === messageId ? { ...m, metadata: { ...m.metadata, rating } } : m);
      setMessages(updated);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updated };
        setConversations(next);
        persistConversations(next);
      }
    } catch (e) {
      console.error('Error sending feedback', e);
      alert('Gagal mengirim feedback');
    }
  };

  // Regenerate (force no-cache) for a specific assistant message: find preceding user message content
  const handleRegenerate = async (assistantIndex) => {
    // find user message before assistantIndex
    let userContent = null;
    for (let i = assistantIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { userContent = messages[i].content; break; }
    }
    if (!userContent) { alert('Tidak menemukan pesan user sebelumnya untuk diregenerasi'); return; }

    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        query: userContent,
        session_id: activeConvId || sessionId,
        use_cache: false,
        k: 5
      }, { timeout: 120000 });

      const assistantMessage = {
        id: `m_${Date.now()+3}`,
        role: 'assistant',
        content: response.data.response,
        metadata: { ...response.data.metadata, regenerated: true },
        cache_used: response.data.cache_used,
        response_time: response.data.response_time,
        timestamp: new Date().toISOString()
      };

      const updatedMessages = [...messages, assistantMessage];
      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }
    } catch (e) {
      console.error('Error regenerating', e);
      alert('Gagal meregenerasi jawaban');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptimizeCache = async () => {
    try {
      const response = await axios.post(`${API_BASE_URL}/optimize`, {
        max_size_mb: 100,
        min_access_count: 2
      });
      alert(`✅ Cache optimized: ${response.data.message || 'Success'}`);
      fetchStats();
    } catch (error) {
      alert('❌ Error optimizing cache');
    }
  };

  const handleClearCache = async () => {
    if (!window.confirm('Are you sure you want to clear all cache?')) return;
    
    try {
      await axios.post(`${API_BASE_URL}/clear`);
      alert('✅ Cache cleared successfully');
      fetchStats();
    } catch (error) {
      alert('❌ Error clearing cache');
    }
  };

  const exampleQueries = [
    "🏖️ Rekomendasi pantai untuk honeymoon budget 10 juta di Toba",
    "⛰️ Tempat wisata gunung untuk hiking pemula di sekitar Danau Toba",
    "👨‍👩‍👧‍👦 Destinasi wisata keluarga dengan anak-anak di Toba",
    "🍜 Kuliner khas Batak yang wajib dicoba di Danau Toba",
    "🏨 Hotel dan penginapan nyaman budget menengah di Toba",
    "📸 Spot foto terbaik untuk Instagram di Danau Toba"
  ];

  const handleShowStats = async () => {
    const data = await fetchStats();
    if (data) {
      setStats(data);
      setShowStats(true);
    }
  };

  const handleExampleClick = (query) => {
    setInput(query);
    inputRef.current?.focus();
  };

  return (
    <div className="app">
      {/* Header dengan user menu */}
      <header className="app-header">
        <div className="header-left">
          <button 
            className="sidebar-toggle" 
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? 'Buka Sidebar' : 'Tutup Sidebar'}
            aria-label="Toggle sidebar"
          >
            {sidebarCollapsed ? <Menu size={24} /> : <ChevronLeft size={24} />}
          </button>
          <img src="/images/logo.png" alt="Toba Logo" className="header-logo" />
          <div className="header-title-group">
            <h1 className="header-title">
              <span className="title-full">Sistem Rekomendasi Wisata Toba</span>
              <span className="title-short">Toba Tourism</span>
            </h1>
            <p className="header-subtitle">Temukan Destinasi Impian Anda di Danau Toba</p>
          </div>
        </div>
        
        <div className="header-right">
          {isAuthenticated ? (
            <div className="user-menu-container" ref={userMenuRef}>
              <button 
                className="user-menu-trigger"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <span className="user-avatar-small">{user?.avatar || '👤'}</span>
                <span className="user-name-header">{user?.name || user?.username}</span>
                <ChevronDown size={16} className={`chevron ${showUserMenu ? 'open' : ''}`} />
              </button>
              
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="dropdown-header">
                    <span className="user-avatar-large">{user?.avatar || '👤'}</span>
                    <div className="dropdown-user-info">
                      <span className="dropdown-name">{user?.name}</span>
                      <span className="dropdown-email">{user?.email || user?.username}</span>
                    </div>
                  </div>
                  <div className="dropdown-divider"></div>
                  <Link to="/profile" className="dropdown-item" onClick={() => setShowUserMenu(false)}>
                    <UserCircle size={18} />
                    <span>Profile Saya</span>
                  </Link>
                  {(isAdmin()) && (
                    <Link to="/admin" className="dropdown-item" onClick={() => setShowUserMenu(false)}>
                      <Settings size={18} />
                      <span>Dashboard Admin</span>
                    </Link>
                  )}
                  <div className="dropdown-divider"></div>
                  <button className="dropdown-item logout-item" onClick={() => { logout(); setShowUserMenu(false); }}>
                    <LogOut size={18} />
                    <span>Keluar</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/login" className="login-btn-header">
              <User size={18} />
              <span>Masuk</span>
            </Link>
          )}
        </div>
      </header>

      <div className={`main-container layout ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Overlay untuk mobile - tutup sidebar ketika klik di luar */}
        {!sidebarCollapsed && (
          <div 
            className="sidebar-overlay" 
            onClick={() => setSidebarCollapsed(true)}
            aria-hidden="true"
          />
        )}
        <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
          {/* Header with New Chat button */}
          <div className="sidebar-header">
            <h3>{!sidebarCollapsed && 'Percakapan'}</h3>
            <div className="sidebar-buttons" style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn-new" onClick={() => createConversation('New')} title="Percakapan Baru">
                <Plus size={sidebarCollapsed ? 18 : 14} />
              </button>
            </div>
          </div>
          
          {/* Conversations list */}
          <div className="conversations-list">
            {!sidebarCollapsed ? (
              <>
                {Object.keys(conversations).length === 0 && (
                  <div className="empty">Belum ada percakapan. Klik + untuk buat.</div>
                )}
                {Object.entries(conversations).map(([id, conv]) => (
                  <div key={id} className={`conv-item ${id === activeConvId ? 'active' : ''}`} onClick={() => selectConversation(id)}>
                    <div className="conv-title">{conv.title || 'Untitled'}</div>
                    <div className="conv-meta">
                      <span>{(conv.messages || []).length} msg</span>
                      <div className="conv-actions">
                        <button onClick={(e)=>{ e.stopPropagation(); renameConversation(id); }}>✎</button>
                        <button onClick={(e)=>{ e.stopPropagation(); deleteConversation(id); }}>🗑</button>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            ) : (
              /* Collapsed - show conversation icons */
              <div className="collapsed-icons">
                {Object.entries(conversations).slice(0, 5).map(([id, conv]) => (
                  <div 
                    key={id} 
                    className={`collapsed-conv-icon ${id === activeConvId ? 'active' : ''}`} 
                    onClick={() => selectConversation(id)}
                    title={conv.title || 'Untitled'}
                  >
                    💬
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* Bottom section - Location & Profile/Login */}
          <div className="sidebar-bottom">
            {/* Location button */}
            <button 
              className={sidebarCollapsed ? "collapsed-conv-icon" : "sidebar-profile-btn"}
              onClick={() => setShowMap(true)} 
              title="Peta Lokasi Wisata"
              style={{ background: 'linear-gradient(135deg, rgba(251, 191, 36, 0.2), rgba(245, 158, 11, 0.15))', border: '1px solid rgba(251, 191, 36, 0.3)' }}
            >
              <MapPin size={sidebarCollapsed ? 20 : 18} style={{ color: '#fbbf24' }} />
              {!sidebarCollapsed && <span className="profile-info" style={{ color: '#fbbf24' }}>Peta Lokasi</span>}
            </button>
            
            {/* Profile/Login button */}
            {isAuthenticated ? (
              <Link 
                to="/profile" 
                className="sidebar-profile-btn"
                title={user?.name || 'Profile'}
              >
                <div className="profile-avatar">
                  {user?.avatar || '👤'}
                </div>
                {!sidebarCollapsed && (
                  <div className="profile-info">
                    <div className="profile-name">{user?.name || 'User'}</div>
                    <div className="profile-status">Lihat Profil</div>
                  </div>
                )}
              </Link>
            ) : (
              <Link to="/login" className="sidebar-login-btn" title="Login">
                <LogIn size={sidebarCollapsed ? 20 : 18} />
                {!sidebarCollapsed && <span>Masuk</span>}
              </Link>
            )}
          </div>
        </aside>

        <div className="chat-container">
          <div className="messages-container">
            {messages.length === 0 && (
              <div className="welcome-message">
                <img src="/images/logo.png" alt="Welcome" className="welcome-icon" />
                <h2>Horas! Selamat Datang di Sistem Rekomendasi Wisata Toba</h2>
                <p>Tanyakan apapun tentang destinasi wisata, kuliner, penginapan, dan aktivitas menarik di Danau Toba</p>
                
                <div className="example-queries">
                  {exampleQueries.map((query, idx) => (
                    <div 
                      key={idx} 
                      className="example-query" 
                      onClick={() => handleExampleClick(query)}
                    >
                      <span className="example-query-icon">💡</span>
                      {query}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={msg.id || idx} className={`message ${msg.role} ${isAuthenticated ? 'with-avatar' : 'no-avatar'}`}>
                <div className="message-content">
                  {/* Avatar hanya tampil jika sudah login */}
                  {isAuthenticated && (
                    <div className={`message-avatar ${msg.role === 'user' ? 'user-avatar' : 'bot-avatar'}`}>
                      {msg.role === 'user' ? (user?.avatar || '👤') : '🤖'}
                    </div>
                  )}
                  <div className="message-body">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                    
                    {/* Show Map if assistant message mentions locations */}
                    {msg.role === 'assistant' && detectLocationMention(msg.content) && locations.length > 0 && (
                      <div style={{ marginTop: '1rem' }}>
                        <div 
                          style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: '0.5rem',
                            marginBottom: '0.75rem',
                            color: '#fbbf24'
                          }}
                        >
                          <MapPin size={18} />
                          <span style={{ fontWeight: '600' }}>Lokasi di Peta</span>
                          <button
                            onClick={() => setShowMap(true)}
                            style={{
                              marginLeft: 'auto',
                              background: 'rgba(251, 191, 36, 0.2)',
                              border: '1px solid #fbbf24',
                              color: '#fbbf24',
                              padding: '0.25rem 0.75rem',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '0.8rem'
                            }}
                          >
                            🗺️ Lihat Peta Lengkap
                          </button>
                        </div>
                        <MapView 
                          locations={locations} 
                          height="280px"
                          showAll={true}
                        />
                      </div>
                    )}
                    
                    {/* Feedback controls - Always show for assistant messages */}
                    {msg.role === 'assistant' && (
                      <div className="message-feedback">
                        <div className="feedback-buttons">
                          <button 
                            title="Jawaban ini membantu" 
                            onClick={() => handleFeedback(msg.id, 1)} 
                            className={`feedback-btn feedback-btn--like ${msg.metadata?.rating === 1 ? 'feedback-btn--active' : ''}`}
                          >
                            <ThumbsUp size={16} />
                          </button>
                          <button 
                            title="Jawaban ini kurang tepat" 
                            onClick={() => handleFeedback(msg.id, -1)} 
                            className={`feedback-btn feedback-btn--dislike ${msg.metadata?.rating === -1 ? 'feedback-btn--active' : ''}`}
                          >
                            <ThumbsDown size={16} />
                          </button>
                          <button 
                            title="Regenerasi jawaban" 
                            onClick={() => handleRegenerate(idx)} 
                            className="feedback-btn feedback-btn--regenerate"
                          >
                            <RefreshCw size={16} />
                          </button>
                        </div>
                        {msg.metadata?.rating && (
                          <span className="feedback-status">
                            {msg.metadata.rating === 1 ? '✓ Terima kasih atas feedback positif!' : '✓ Feedback tercatat, kami akan perbaiki'}
                          </span>
                        )}
                      </div>
                    )}
                    
                    {/* Metadata info */}
                    {msg.metadata && msg.metadata.response_time && (
                      <div className="message-metadata">
                        {msg.timestamp && <span>⏰ {msg.timestamp}</span>}
                        <span className={`source-badge ${msg.metadata.cache_used ? 'cached' : 'generated'}`}>
                          {msg.metadata.cache_used ? '⚡ Cached' : '🔍 Generated'}
                        </span>
                        <span>⏱️ {msg.metadata.response_time.toFixed(2)}s</span>
                        {msg.metadata.num_chunks > 0 && (
                          <span>📄 {msg.metadata.num_chunks} chunks</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className={`message assistant ${isAuthenticated ? 'with-avatar' : 'no-avatar'}`}>
                <div className="message-content">
                  {isAuthenticated && (
                    <div className="message-avatar bot-avatar">🤖</div>
                  )}
                  <div className="message-body">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="input-form">
            <div className="input-wrapper">
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="⌨️ Tanyakan tentang wisata Danau Toba..."
                disabled={isLoading}
                className="input-field"
                rows={1}
              />
              <button 
                type="submit" 
                disabled={isLoading || !input.trim()}
                className="send-button"
              >
                {isLoading ? (
                  <>
                    <div className="loading-dot"></div>
                    <div className="loading-dot"></div>
                    <div className="loading-dot"></div>
                  </>
                ) : (
                  <>
                    <Send size={20} />
                    <span>Kirim</span>
                  </>
                )}
              </button>
            </div>
            <div className="input-disclaimer">
              Toba AI dapat membuat kesalahan. Periksa info penting sebelum mengambil keputusan.
            </div>
          </form>
        </div>
      </div>

      {showStats && stats && (
        <div className="modal-overlay" onClick={() => setShowStats(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">
                <TrendingUp size={32} />
                Cache Statistics
              </h2>
              <button onClick={() => setShowStats(false)} className="close-button">
                ✕
              </button>
            </div>
            
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">
                  <Database size={16} />
                  Total Cached Items
                </div>
                <div className="stat-value">{stats.total_cached_items || 0}</div>
                <div className="stat-description">Queries stored in cache</div>
              </div>
              
              <div className="stat-card">
                <div className="stat-label">
                  <Server size={16} />
                  Cache Size
                </div>
                <div className="stat-value">{stats.total_size_mb || 0} MB</div>
                <div className="stat-description">Total storage used</div>
              </div>
              
              <div className="stat-card">
                <div className="stat-label">
                  ⚡ Cache Hit Rate
                </div>
                <div className="stat-value">
                  {stats.cache_hit_rate ? `${stats.cache_hit_rate.toFixed(1)}%` : 'N/A'}
                </div>
                <div className="stat-description">Percentage of cached responses</div>
              </div>
              
              <div className="stat-card">
                <div className="stat-label">
                  ⏱️ Avg Response Time
                </div>
                <div className="stat-value">
                  {stats.avg_response_time ? `${stats.avg_response_time.toFixed(2)}s` : 'N/A'}
                </div>
                <div className="stat-description">Average query processing time</div>
              </div>
            </div>

            {stats.most_accessed && stats.most_accessed.length > 0 && (
              <div style={{ marginTop: '2rem' }}>
                <h3 style={{ color: 'var(--batak-gold)', marginBottom: '1rem', fontSize: '1.3rem' }}>
                  🔥 Most Popular Queries
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {stats.most_accessed.map((item, idx) => (
                    <div 
                      key={idx}
                      style={{
                        background: 'rgba(30, 41, 59, 0.6)',
                        padding: '1rem',
                        borderRadius: '8px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        border: '1px solid rgba(220, 38, 38, 0.3)'
                      }}
                    >
                      <span style={{ color: 'rgba(255, 255, 255, 0.9)' }}>{item.query}</span>
                      <span 
                        style={{
                          background: 'rgba(220, 38, 38, 0.3)',
                          padding: '0.3rem 0.8rem',
                          borderRadius: '12px',
                          color: 'var(--batak-gold)',
                          fontWeight: '600',
                          fontSize: '0.85rem'
                        }}
                      >
                        {item.access_count} hits
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
              <button onClick={handleOptimizeCache} className="btn-stats" style={{ flex: 1 }}>
                ⚡ Optimize Cache
              </button>
              <button 
                onClick={handleClearCache} 
                className="btn-stats" 
                style={{ 
                  flex: 1, 
                  background: 'linear-gradient(135deg, #ef4444, #b91c1c)' 
                }}
              >
                🗑️ Clear Cache
              </button>
            </div>
            
            {/* Map Button in Stats Modal */}
            <button 
              onClick={() => { setShowStats(false); setShowMap(true); }}
              className="btn-stats"
              style={{ 
                width: '100%',
                marginTop: '1rem',
                background: 'linear-gradient(135deg, #fbbf24, #f59e0b)'
              }}
            >
              🗺️ Lihat Peta Wisata Toba ({locations.length} lokasi)
            </button>
          </div>
        </div>
      )}

      {/* Full Map Modal */}
      {showMap && (
        <div className="modal-overlay" onClick={() => setShowMap(false)}>
          <div 
            className="modal-content" 
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '95vw', width: '1100px' }}
          >
            <div className="modal-header">
              <h2 className="modal-title">
                <MapPin size={28} style={{ color: '#fbbf24' }} />
                Peta Wisata Danau Toba
              </h2>
              <button onClick={() => setShowMap(false)} className="close-button">
                ✕
              </button>
            </div>
            
            <MapView 
              locations={locations} 
              height="550px" 
              showAll={true}
            />
            
            <div style={{ 
              marginTop: '1rem', 
              padding: '1rem',
              background: 'rgba(30, 41, 59, 0.6)',
              borderRadius: '8px',
              color: 'rgba(255, 255, 255, 0.8)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <p style={{ margin: 0, fontWeight: '600', color: '#fbbf24' }}>
                    📍 {locations.length} lokasi wisata
                  </p>
                  <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem' }}>
                    Klik marker merah untuk detail lokasi. Klik "Open in Google Maps" untuk navigasi.
                  </p>
                </div>
                <button
                  onClick={async () => {
                    try {
                      await axios.post(`${API_BASE_URL}/extract-locations`);
                      await fetchLocations();
                      alert('✅ Lokasi berhasil di-update dari PDF!');
                    } catch (e) {
                      alert('❌ Gagal extract lokasi: ' + e.message);
                    }
                  }}
                  style={{
                    background: 'linear-gradient(135deg, #dc2626, #991b1b)',
                    border: 'none',
                    color: 'white',
                    padding: '0.5rem 1rem',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    fontWeight: '500'
                  }}
                >
                  🔄 Refresh dari PDF
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
