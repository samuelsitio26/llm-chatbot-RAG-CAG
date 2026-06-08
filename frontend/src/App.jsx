import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import { Send, TrendingUp, Server, Database, ThumbsUp, ThumbsDown, RefreshCw, Plus, MapPin, LogIn, Settings, User, LogOut, ChevronLeft, ChevronRight, ChevronDown, UserCircle, Menu, X, Copy, Check, Star, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import MapView from './MapView';
import 'leaflet/dist/leaflet.css';
import { useAuth } from './context/AuthContext';

// ✅ Use relative URL - Vite will proxy to backend
const API_BASE_URL = '/api';

console.log('🔗 API URL:', API_BASE_URL);

// Helper function to check if avatar is an image URL
const isImageAvatar = (avatar) => {
  return avatar && (
    avatar.startsWith('/api/avatars/') || 
    avatar.startsWith('data:image') || 
    avatar.startsWith('http://') ||
    avatar.startsWith('https://')
  );
};

// Avatar component that handles both emoji and image URLs
const Avatar = ({ src, size = 'small', className = '' }) => {
  const [imageError, setImageError] = React.useState(false);
  
  // Reset error state when src changes
  React.useEffect(() => {
    setImageError(false);
  }, [src]);
  
  if (isImageAvatar(src) && !imageError) {
    return (
      <img 
        src={src} 
        alt="Avatar" 
        className={`avatar-img avatar-${size} ${className}`}
        crossOrigin="anonymous"
        referrerPolicy="no-referrer"
        onError={() => setImageError(true)}
      />
    );
  }
  return <span className={`avatar-emoji avatar-${size} ${className}`}>{src || '👤'}</span>;
};

function App() {
  const { user, token, isAuthenticated, logout, updateUserStats, isAdmin } = useAuth();

  // Helper: build Authorization header when user is logged in
  const getAuthHeaders = () => token ? { Authorization: `Bearer ${token}` } : {};
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
  const [mapFilter, setMapFilter] = useState(null);

  // Example queries dari FAQ
  const [exampleQueries, setExampleQueries] = useState([
    "🏖️ Rekomendasi pantai untuk honeymoon budget 10 juta di Toba",
    "⛰️ Tempat wisata gunung untuk hiking pemula di sekitar Danau Toba",
    "👨‍👩‍👧‍👦 Destinasi wisata keluarga dengan anak-anak di Toba",
    "🍜 Kuliner khas Batak yang wajib dicoba di Danau Toba",
    "🏨 Hotel dan penginapan nyaman budget menengah di Toba",
    "📸 Spot foto terbaik untuk Instagram di Danau Toba"
  ]);

  // Quick Replies / FAQ Suggestions state
  const [allFaqQuestions, setAllFaqQuestions] = useState([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const faqPoolRef = useRef([]); // stable ref to avoid stale closure in async callbacks
  
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

  // Emoji mapping berdasarkan kata kunci di pertanyaan FAQ
  const getEmojiForQuestion = (q) => {
    const ql = q.toLowerCase();
    if (ql.includes('pantai') || ql.includes('beach'))          return '🏖️';
    if (ql.includes('hotel') || ql.includes('penginapan') || ql.includes('villa') || ql.includes('homestay')) return '🏨';
    if (ql.includes('makan') || ql.includes('restoran') || ql.includes('kuliner') || ql.includes('cafe') || ql.includes('khas')) return '🍜';
    if (ql.includes('air terjun') || ql.includes('bukit') || ql.includes('gunung') || ql.includes('hiking')) return '⛰️';
    if (ql.includes('samosir') || ql.includes('pulau'))         return '🏝️';
    if (ql.includes('harga') || ql.includes('biaya') || ql.includes('budget') || ql.includes('tarif')) return '💰';
    if (ql.includes('foto') || ql.includes('instagram') || ql.includes('spot')) return '📸';
    if (ql.includes('anak') || ql.includes('keluarga'))        return '👨‍👩‍👧‍👦';
    if (ql.includes('transport') || ql.includes('ferry') || ql.includes('cara ke')) return '🚢';
    if (ql.includes('museum') || ql.includes('budaya') || ql.includes('batak')) return '🏛️';
    if (ql.includes('fasilitas') || ql.includes('kolam') || ql.includes('wifi')) return '✨';
    if (ql.includes('jarak') || ql.includes('mengemudi') || ql.includes('menit')) return '📍';
    return '💡';
  };

  // Fetch 6 pertanyaan acak dari FAQ sebagai example queries
  const fetchExampleQueries = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/faqs`);
      const faqs = (res.data.faqs || []).filter(f => f.question?.trim());
      if (faqs.length === 0) return;
      // Simpan semua FAQ untuk digunakan sebagai quick replies
      setAllFaqQuestions(faqs);
      faqPoolRef.current = faqs; // stable ref untuk async callbacks
      // Acak dan ambil 6 untuk welcome screen
      const shuffled = [...faqs].sort(() => Math.random() - 0.5);
      const picked = shuffled.slice(0, 6).map(f => {
        const emoji = getEmojiForQuestion(f.question);
        return `${emoji} ${f.question}`;
      });
      setExampleQueries(picked);
      // Set initial quick replies (4 pertanyaan acak)
      pickSuggestedQuestions(faqs);
    } catch (err) {
      console.warn('⚠️ Gagal load FAQ untuk example queries:', err.message);
      // Biarkan fallback default tetap tampil
    }
  };

  // Pilih N pertanyaan acak dari FAQ pool untuk quick replies
  const pickSuggestedQuestions = (pool, count = 4) => {
    // Gunakan pool yang diberikan, atau fallback ke ref (stabil di async callbacks)
    const source = pool || faqPoolRef.current;
    if (!source || source.length === 0) return;
    const shuffled = [...source].sort(() => Math.random() - 0.5);
    const picked = shuffled.slice(0, count).map(f => ({
      text: f.question,
      emoji: getEmojiForQuestion(f.question),
    }));
    setSuggestedQuestions(picked);
  };

  // Handle quick reply click - langsung submit pertanyaan
  const handleQuickReply = (question) => {
    if (isLoading) return;
    // Cek apakah ada comparison yang belum diselesaikan
    const pendingComparison = messages.some(
      m => m.role === 'assistant' && m.variants && m.chosenVariant === undefined
    );
    if (pendingComparison) return;
    handleSubmitWithQuery(question);
  };

  // Submit dengan query spesifik (untuk quick replies)
  const handleSubmitWithQuery = async (queryText) => {
    if (!queryText.trim() || isLoading) return;

    const userMessage = {
      id: `m_${Date.now()}`,
      role: 'user',
      content: queryText,
      timestamp: new Date().toISOString()
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    if (activeConvId) {
      const next = { ...conversations };
      next[activeConvId] = { ...next[activeConvId], messages: newMessages };
      setConversations(next);
      persistConversations(next);
    }

    setIsLoading(true);
    setSuggestedQuestions([]); // Sembunyikan quick replies saat loading

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        query: queryText,
        session_id: sessionId,
        conversation_id: activeConvId,
        use_cache: true,
        k: 8,
        max_new_tokens: 2048,
        temperature: 0.7,
        favorite_categories: user?.favoriteCategories || []
      }, {
        headers: getAuthHeaders(),
        timeout: 120000
      });

      const assistantMessage = {
        id: `m_${Date.now()+1}`,
        role: 'assistant',
        content: response.data.response,
        metadata: {
          ...(response.data.metadata || {}),
          cache_key: response.data.cache_key || null,
          chat_db_id: response.data.chat_db_id || null,
        },
        source: response.data.source,
        cache_used: response.data.cache_used,
        response_time: response.data.response_time,
        relevant_locations: response.data.sources || [],
        timestamp: new Date().toISOString(),
      };

      const updatedMessages = [...newMessages, assistantMessage];
      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }

      if (isAuthenticated && updateUserStats) {
        updateUserStats('chat', { query: queryText });
      }
      // Refresh quick replies setelah mendapat jawaban
      pickSuggestedQuestions();
    } catch (error) {
      console.error('❌ Error:', error);
      const errorMessage = {
        id: `m_${Date.now()+2}`,
        role: 'assistant',
        content: `Maaf, terjadi kesalahan: ${error.response?.data?.detail || error.message || 'Network error'}.`,
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
      pickSuggestedQuestions();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLocations(); // Load map locations on mount
    fetchExampleQueries(); // Load example queries dari FAQ
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

  // Load conversations — from SERVER for logged-in users, localStorage for guests
  useEffect(() => {
    const loadConversations = async () => {
      try {
        if (isAuthenticated && token) {
          // ── Logged-in: load from server (single source of truth) ──
          const res = await axios.get(`${API_BASE_URL}/conversations`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const serverConvs = res.data.conversations || [];
          if (serverConvs.length > 0) {
            const mapped = {};
            serverConvs.forEach(c => {
              mapped[c.id] = { id: c.id, title: c.title, messages: [] };
            });
            setConversations(mapped);

            let restoredId = null;
            try {
              const lastRes = await axios.get(`${API_BASE_URL}/conversations/last`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              const lastConv = lastRes.data?.conversation;
              if (lastConv?.id && mapped[lastConv.id]) {
                restoredId = lastConv.id;
              }
            } catch (lastErr) {
              console.warn('⚠️ Could not restore last conversation from DB:', lastErr.message);
            }

            setActiveConvId(restoredId || serverConvs[0].id);
          } else {
            // No conversations on server — start fresh
            const id = `conv_${Date.now()}`;
            setConversations({ [id]: { id, title: 'General', messages: [] } });
            setActiveConvId(id);
          }
          // Clean up stale localStorage for this user
          localStorage.removeItem(`toba_conversations_user_${user.id}`);
        } else {
          // ── Guest: use localStorage ──
          const saved = localStorage.getItem('toba_conversations_guest');
          if (saved) {
            const parsed = JSON.parse(saved);
            setConversations(parsed);
            const ids = Object.keys(parsed);
            if (ids.length > 0) setActiveConvId(ids[0]);
          } else {
            const id = `conv_${Date.now()}`;
            const init = { [id]: { id, title: 'General', messages: [] } };
            setConversations(init);
            setActiveConvId(id);
          }
        }
      } catch (e) {
        console.error('Error loading conversations', e);
        // Fallback: start fresh
        const id = `conv_${Date.now()}`;
        setConversations({ [id]: { id, title: 'General', messages: [] } });
        setActiveConvId(id);
      }
    };
    loadConversations();
  }, [user?.id, isAuthenticated, token]);

  // When switching conversation, load messages from server for logged-in users
  useEffect(() => {
    if (!activeConvId) return;

    const loadMessages = async () => {
      if (isAuthenticated && token) {
        // Check if we already have messages loaded in memory for this conv
        const conv = conversations[activeConvId];
        if (conv && conv.messages && conv.messages.length > 0) {
          setMessages(conv.messages);
          return;
        }
        // Check localStorage enriched cache first (preserves relevant_locations for maps)
        try {
          const cached = localStorage.getItem(msgCacheKey);
          if (cached) {
            const cacheMap = JSON.parse(cached);
            if (cacheMap[activeConvId] && cacheMap[activeConvId].length > 0) {
              const cachedMsgs = cacheMap[activeConvId];
              setMessages(cachedMsgs);
              setConversations(prev => ({
                ...prev,
                [activeConvId]: { ...prev[activeConvId], messages: cachedMsgs },
              }));
              return;
            }
          }
        } catch (e) {
          // ignore cache read errors, fall through to server fetch
        }
        // Fetch from server (fallback — no relevant_locations, map won't show for old msgs)
        try {
          const res = await axios.get(
            `${API_BASE_URL}/conversations/${activeConvId}/history`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          const history = res.data.history || [];
          // Convert server format [{role, content}] to frontend message format
          const msgs = history.map((h, i) => ({
            id: `m_db_${i}`,
            role: h.role,
            content: h.content,
            timestamp: new Date().toISOString(),
            metadata: {},
          }));
          setMessages(msgs);
          // Cache in local state so we don't re-fetch on every switch
          setConversations(prev => ({
            ...prev,
            [activeConvId]: { ...prev[activeConvId], messages: msgs },
          }));
        } catch (e) {
          console.error('Error loading conversation history', e);
          setMessages([]);
        }
      } else {
        // Guest: sync from local state
        const conv = conversations[activeConvId];
        if (conv) setMessages(conv.messages || []);
      }
    };
    loadMessages();
  }, [activeConvId]);

  // Persist conversations — only localStorage for guests
  // localStorage key for enriched message data (relevant_locations, metadata, etc.)  
  const msgCacheKey = isAuthenticated && user?.id
    ? `toba_msgcache_${user.id}`
    : 'toba_msgcache_guest';

  const persistConversations = (next) => {
    if (!isAuthenticated) {
      try {
        localStorage.setItem('toba_conversations_guest', JSON.stringify(next));
      } catch (e) {
        console.error('Error saving conversations', e);
      }
    }
    // Always cache enriched messages (incl. relevant_locations) for map restore on refresh
    try {
      const cache = {};
      Object.values(next).forEach(conv => {
        if (conv.messages && conv.messages.length > 0) {
          cache[conv.id] = conv.messages;
        }
      });
      localStorage.setItem(msgCacheKey, JSON.stringify(cache));
    } catch (e) {
      console.error('Error caching messages', e);
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
        conversation_id: activeConvId,  // link Q&A to this conversation thread in DB
        use_cache: true,
        k: 8,
        max_new_tokens: 2048,
        temperature: 0.7,
        favorite_categories: user?.favoriteCategories || []
      }, {
        headers: getAuthHeaders(),
        timeout: 120000 // 2 minute timeout for generation
      });

      console.log('✅ Response:', response.data);

      const assistantMessage = {
        id: `m_${Date.now()+1}`,
        role: 'assistant',
        content: response.data.response,
        metadata: {
          ...(response.data.metadata || {}),
          cache_key: response.data.cache_key || null,  // for feedback routing
          chat_db_id: response.data.chat_db_id || null, // real PK from chat_history → valid FK for feedback
        },
        source: response.data.source,
        cache_used: response.data.cache_used,
        response_time: response.data.response_time,
        relevant_locations: response.data.sources || [], // Locations mentioned in response
        timestamp: new Date().toISOString(),
      };

      const updatedMessages = [...newMessages, assistantMessage];
      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }

      // Log relevant locations
      if (response.data.sources && response.data.sources.length > 0) {
        console.log(`🗺️ Response contains ${response.data.sources.length} relevant locations`);
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
      // Refresh quick replies setelah mendapat jawaban
      pickSuggestedQuestions();
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

  const selectConversation = async (id) => {
    setActiveConvId(id);

    if (isAuthenticated && token) {
      try {
        await axios.post(
          `${API_BASE_URL}/conversations/${id}/activate`,
          {},
          { headers: getAuthHeaders() }
        );
      } catch (e) {
        console.warn('⚠️ Failed to mark conversation active:', e.message);
      }
    }
  };

  const renameConversation = (id) => {
    const name = window.prompt('Nama percakapan (mis. Parapat, Tuk-Tuk, Tomok):', conversations[id].title || 'Conversation');
    if (!name) return;
    const next = { ...conversations };
    next[id] = { ...next[id], title: name };
    setConversations(next);
    persistConversations(next);
  };

  const deleteConversation = async (id) => {
    if (!window.confirm('Hapus percakapan ini?')) return;

    // Delete from server if logged in
    if (isAuthenticated && token) {
      try {
        await axios.delete(`${API_BASE_URL}/conversations/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (e) {
        console.error('Error deleting conversation from server', e);
      }
    }

    const next = { ...conversations };
    delete next[id];
    setConversations(next);
    persistConversations(next);
    const ids = Object.keys(next);
    setActiveConvId(ids.length > 0 ? ids[0] : null);
  };

  // Feedback (thumbs up/down) — toggle behaviour like ChatGPT
  const handleFeedback = async (messageId, clickedRating) => {
    const targetMsg = messages.find(m => m.id === messageId);
    const cacheKey = targetMsg?.metadata?.cache_key || null;
    const currentRating = targetMsg?.metadata?.rating || 0;

    // Optimistic toggle: same rating → 0, different → new
    const newRating = currentRating === clickedRating ? 0 : clickedRating;

    // Optimistic UI update
    const updated = messages.map(m =>
      m.id === messageId
        ? { ...m, metadata: { ...m.metadata, rating: newRating } }
        : m
    );
    setMessages(updated);
    if (activeConvId) {
      const next = { ...conversations };
      next[activeConvId] = { ...next[activeConvId], messages: updated };
      setConversations(next);
      persistConversations(next);
    }

    try {
      const res = await axios.post(`${API_BASE_URL}/feedback`, {
        session_id: activeConvId || sessionId,
        message_id: messageId,
        rating: clickedRating,
        cache_key: cacheKey,
        chat_db_id: targetMsg?.metadata?.chat_db_id || null,
      }, { headers: getAuthHeaders() });

      // Server may return a different final rating (toggle logic)
      const serverRating = res.data.rating;
      if (serverRating !== newRating) {
        const corrected = messages.map(m =>
          m.id === messageId
            ? { ...m, metadata: { ...m.metadata, rating: serverRating } }
            : m
        );
        setMessages(corrected);
        if (activeConvId) {
          const next2 = { ...conversations };
          next2[activeConvId] = { ...next2[activeConvId], messages: corrected };
          setConversations(next2);
          persistConversations(next2);
        }
      }
    } catch (e) {
      console.error('Error sending feedback', e);
      // Revert optimistic update
      setMessages(messages);
    }
  };

  // Copy answer text to clipboard
  const handleCopy = async (text, messageId) => {
    try {
      await navigator.clipboard.writeText(text);
      // Set copied state temporarily
      const updated = messages.map(m =>
        m.id === messageId ? { ...m, metadata: { ...m.metadata, copied: true } } : m
      );
      setMessages(updated);
      setTimeout(() => {
        setMessages(prev => prev.map(m =>
          m.id === messageId ? { ...m, metadata: { ...m.metadata, copied: false } } : m
        ));
      }, 2000);
    } catch (e) {
      console.error('Copy failed', e);
    }
  };

  // Regenerate: get new answer and show comparison for user to choose
  const handleRegenerate = async (assistantIndex) => {
    const assistantMsg = messages[assistantIndex];
    // Find user message that preceded this assistant message
    let userContent = null;
    for (let i = assistantIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { userContent = messages[i].content; break; }
    }
    if (!userContent) { alert('Tidak menemukan pesan user sebelumnya untuk diregenerasi'); return; }

    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/chat/regenerate`, {
        question: userContent,
        old_answer: assistantMsg.content,
        cache_key: assistantMsg.metadata?.cache_key || null,
        conversation_id: activeConvId,
      }, {
        headers: getAuthHeaders(),
        timeout: 120000
      });

      const { old_answer, new_answer, variants, cache_key } = response.data;

      // Update the assistant message to show comparison mode
      const updatedMsg = {
        ...assistantMsg,
        metadata: {
          ...assistantMsg.metadata,
          cache_key: cache_key || assistantMsg.metadata?.cache_key,
          rating: undefined,  // reset feedback
        },
        variants: variants || [
          { id: -1, answer: old_answer, source: 'original', votes: 0 },
          { id: -2, answer: new_answer, source: 'regenerated', votes: 0 },
        ],
        chosenVariant: undefined,  // user hasn't chosen yet
        timestamp: new Date().toISOString(),
      };

      const updatedMessages = messages.map((m, i) =>
        i === assistantIndex ? updatedMsg : m
      );

      setMessages(updatedMessages);
      if (activeConvId) {
        const next = { ...conversations };
        next[activeConvId] = { ...next[activeConvId], messages: updatedMessages };
        setConversations(next);
        persistConversations(next);
      }
    } catch (e) {
      console.error('Error regenerating', e);
      alert(`Gagal meregenerasi jawaban: ${e.response?.data?.detail || e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Choose a variant from comparison
  const handleChooseVariant = async (messageId, variantIndex) => {
    const targetMsg = messages.find(m => m.id === messageId);
    if (!targetMsg?.variants?.[variantIndex]) return;

    const chosenVariant = targetMsg.variants[variantIndex];

    // Optimistic UI update — show chosen answer immediately
    const updated = messages.map(m =>
      m.id === messageId
        ? {
            ...m,
            content: chosenVariant.answer,
            chosenVariant: variantIndex,
            metadata: { ...m.metadata, rating: undefined },
          }
        : m
    );
    setMessages(updated);
    if (activeConvId) {
      const next = { ...conversations };
      next[activeConvId] = { ...next[activeConvId], messages: updated };
      setConversations(next);
      persistConversations(next);
    }

    // Send vote to backend — also updates KV cache with the chosen answer
    try {
      await axios.post(`${API_BASE_URL}/chat/choose-variant`, {
        variant_id: chosenVariant.id,
        question_hash: targetMsg.metadata?.cache_key || null,
        chosen_answer: chosenVariant.answer,
      }, { headers: getAuthHeaders() });
    } catch (e) {
      console.error('Error voting variant', e);
    }
  };

  // Check if there's a pending comparison that hasn't been resolved
  const hasPendingComparison = messages.some(
    m => m.role === 'assistant' && m.variants && m.chosenVariant === undefined
  );

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

  // exampleQueries sekarang berasal dari state (diisi oleh fetchExampleQueries di useEffect)

  const handleShowStats = async () => {
    const data = await fetchStats();
    if (data) {
      setStats(data);
      setShowStats(true);
    }
  };

  const handleExampleClick = (query) => {
    // Strip leading emoji + space before sending — emojis are display-only
    const clean = query.indexOf(' ') !== -1 ? query.substring(query.indexOf(' ') + 1) : query;
    setInput(clean);
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
                <Avatar src={user?.avatar} size="small" className="user-avatar-small" />
                <span className="user-name-header">{user?.name || user?.username}</span>
                <ChevronDown size={16} className={`chevron ${showUserMenu ? 'open' : ''}`} />
              </button>
              
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="dropdown-header">
                    <Avatar src={user?.avatar} size="large" className="user-avatar-large" />
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
                  <Avatar src={user?.avatar} size="medium" />
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
                      <Sparkles size={16} className="example-query-icon" />
                      {query}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={msg.id || idx} className={`message ${msg.role} ${isAuthenticated ? 'with-avatar' : 'no-avatar'}`}>
                {/* Avatar hanya tampil jika sudah login */}
                {isAuthenticated && (
                  <div className={`message-avatar ${msg.role === 'user' ? 'user-avatar' : 'bot-avatar'}`}>
                    {msg.role === 'user' ? <Avatar src={user?.avatar} size="message" /> : '🤖'}
                  </div>
                )}
                <div className="message-content">
                  <div className="message-body">

                    {/* ═══════ COMPARISON MODE: variants exist, user hasn't chosen ═══════ */}
                    {msg.role === 'assistant' && msg.variants && msg.chosenVariant === undefined ? (
                      <div className="answer-comparison">
                        <div className="comparison-header">
                          <RefreshCw size={18} />
                          <span>Pilih jawaban yang paling baik untuk pertanyaan ini:</span>
                        </div>
                        <div className="comparison-cards">
                          {msg.variants.slice(0, 2).map((v, vi) => (
                            <div key={v.id || vi} className="variant-card">
                              <div className="variant-label">
                                {vi === 0 ? '🅰️ Jawaban A' : '🅱️ Jawaban B'}
                                <span className="variant-source">
                                  {v.source === 'original' ? '(Original)' : v.source === 'regenerated' ? '(Baru)' : `(${v.source})`}
                                </span>
                              </div>
                              <div className="variant-body">
                                <ReactMarkdown>{v.answer}</ReactMarkdown>
                              </div>
                              <div className="variant-footer">
                                <span className="variant-votes">
                                  <Star size={14} /> {v.votes || 0} pilihan
                                </span>
                                <button
                                  className="variant-choose-btn"
                                  onClick={() => handleChooseVariant(msg.id, vi)}
                                >
                                  <ThumbsUp size={14} />
                                  Pilih Jawaban Ini
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="comparison-hint">
                          ⚠️ Pilih salah satu jawaban untuk melanjutkan percakapan
                        </div>
                      </div>
                    ) : (
                      /* ═══════ NORMAL MODE: single answer ═══════ */
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    )}
                    
                    {/* Show Map only if response has relevant locations (1-3 locations) */}
                    {msg.role === 'assistant' && msg.relevant_locations && msg.relevant_locations.length > 0 && (
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
                          <span style={{ fontWeight: '600' }}>
                            {msg.relevant_locations.length} Lokasi Rekomendasi
                          </span>
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
                            🗺️ Lihat Semua Lokasi ({locations.length})
                          </button>
                        </div>
                        {/* Show only relevant locations (1-3) mentioned in response */}
                        <MapView 
                          locations={msg.relevant_locations} 
                          height="280px"
                          showAll={true}
                        />
                        <div style={{ 
                          marginTop: '0.5rem', 
                          fontSize: '0.8rem', 
                          color: 'rgba(255,255,255,0.6)',
                          fontStyle: 'italic'
                        }}>
                          💡 Menampilkan {msg.relevant_locations.length} dari {locations.length} lokasi berdasarkan rekomendasi
                        </div>
                      </div>
                    )}
                    
                    {/* ═══════ ChatGPT-style Action Toolbar ═══════ */}
                    {msg.role === 'assistant' && (!msg.variants || msg.chosenVariant !== undefined) && (
                      <div className="message-actions-toolbar">
                        {/* Like */}
                        <button 
                          title={msg.metadata?.rating === 1 ? "Batal suka" : "Jawaban ini membantu"}
                          onClick={() => handleFeedback(msg.id, 1)} 
                          className={`action-icon-btn ${msg.metadata?.rating === 1 ? 'action-icon-btn--active-like' : ''}`}
                        >
                          <ThumbsUp size={15} />
                        </button>

                        {/* Dislike */}
                        <button 
                          title={msg.metadata?.rating === -1 ? "Batal tidak suka" : "Jawaban ini kurang tepat"}
                          onClick={() => handleFeedback(msg.id, -1)} 
                          className={`action-icon-btn ${msg.metadata?.rating === -1 ? 'action-icon-btn--active-dislike' : ''}`}
                        >
                          <ThumbsDown size={15} />
                        </button>

                        {/* Copy */}
                        <button 
                          title="Salin jawaban"
                          onClick={() => handleCopy(msg.content, msg.id)} 
                          className={`action-icon-btn ${msg.metadata?.copied ? 'action-icon-btn--copied' : ''}`}
                        >
                          {msg.metadata?.copied ? <Check size={15} /> : <Copy size={15} />}
                        </button>

                        {/* Regenerate */}
                        <button 
                          title="Regenerasi jawaban"
                          onClick={() => handleRegenerate(idx)} 
                          className="action-icon-btn"
                          disabled={isLoading}
                        >
                          <RefreshCw size={15} className={isLoading ? 'spin-icon' : ''} />
                        </button>

                        {/* Feedback status text */}
                        {msg.metadata?.rating === 1 && (
                          <span className="action-status action-status--like">Terima kasih!</span>
                        )}
                        {msg.metadata?.rating === -1 && (
                          <span className="action-status action-status--dislike">Feedback tercatat</span>
                        )}
                        {msg.metadata?.copied && (
                          <span className="action-status action-status--copy">Tersalin!</span>
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

          {/* ═══════ Quick Replies / FAQ Suggestions ═══════ */}
          {!isLoading && suggestedQuestions.length > 0 && messages.length > 0 && !hasPendingComparison && (
            <div className="quick-replies-wrapper">
              <div className="quick-replies-label">
                <Sparkles size={13} />
                <span>Pertanyaan yang mungkin ingin Anda tanyakan</span>
              </div>
              <div className="quick-replies-list">
                {suggestedQuestions.map((q, i) => (
                  <button
                    key={i}
                    className="quick-reply-btn"
                    onClick={() => handleQuickReply(q.text)}
                    title={q.text}
                  >
                    <span className="quick-reply-emoji">{q.emoji}</span>
                    <span className="quick-reply-text">{q.text}</span>
                  </button>
                ))}
                <button
                  className="quick-reply-btn quick-reply-refresh"
                  onClick={() => pickSuggestedQuestions()}
                  title="Tampilkan pertanyaan lain"
                >
                  <RefreshCw size={13} />
                  <span>Lainnya</span>
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className={`input-form ${hasPendingComparison ? 'input-form--blocked' : ''}`}>
            {hasPendingComparison && (
              <div className="input-blocked-notice">
                ⚠️ Pilih salah satu jawaban di atas sebelum melanjutkan
              </div>
            )}
            <div className="input-wrapper">
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={hasPendingComparison ? "Pilih jawaban terlebih dahulu..." : "⌨️ Tanyakan tentang wisata Danau Toba..."}
                disabled={isLoading || hasPendingComparison}
                className="input-field"
                rows={1}
              />
              <button 
                type="submit" 
                disabled={isLoading || !input.trim() || hasPendingComparison}
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
            style={{ maxWidth: '90vw', width: '740px' }}
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
              height="370px" 
              showAll={true}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
