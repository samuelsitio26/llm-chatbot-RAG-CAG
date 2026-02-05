import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

// API Base URL - Use relative URL for production, absolute for development
const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000/api' : '/api';

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Helper function for API calls
const apiCall = async (endpoint, method = 'GET', body = null, token = null) => {
  const headers = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const config = {
    method,
    headers,
  };
  
  if (body) {
    config.body = JSON.stringify(body);
  }
  
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'API Error');
    }
    
    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

// Fallback to localStorage if backend is not available
const getStoredUsers = () => {
  try {
    const stored = localStorage.getItem('toba_users_db');
    if (stored) return JSON.parse(stored);
  } catch (e) {}
  
  // Default users
  return [
    { id: 1, username: 'admin', password: 'admin123', role: 'admin', name: 'Administrator', avatar: '👨‍💼', createdAt: new Date().toISOString() },
    { id: 2, username: 'operator', password: 'operator123', role: 'operator', name: 'Operator', avatar: '👷', createdAt: new Date().toISOString() }
  ];
};

const saveUsersDB = (users) => {
  localStorage.setItem('toba_users_db', JSON.stringify(users));
};

// User activity log untuk admin
const logUserActivity = (userId, username, action, details = {}) => {
  try {
    const logs = JSON.parse(localStorage.getItem('toba_user_activity') || '[]');
    logs.unshift({
      id: Date.now(),
      userId,
      username,
      action,
      details,
      timestamp: new Date().toISOString()
    });
    // Keep only last 500 logs
    localStorage.setItem('toba_user_activity', JSON.stringify(logs.slice(0, 500)));
  } catch (e) {}
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false); // Flag untuk memastikan auth sudah dicek
  const [allUsers, setAllUsers] = useState([]);
  const [backendAvailable, setBackendAvailable] = useState(false);

  // Check backend availability and validate token
  useEffect(() => {
    const initAuth = async () => {
      console.log('🔐 Initializing auth...');
      const savedToken = localStorage.getItem('toba_auth_token');
      const savedUser = localStorage.getItem('toba_current_user');
      
      // PENTING: Restore user dari localStorage DULU untuk menghindari flicker
      if (savedUser) {
        try {
          const userData = JSON.parse(savedUser);
          setUser(userData);
          console.log('✅ User restored from localStorage:', userData.username);
        } catch (e) {
          console.log('❌ Failed to parse saved user');
          localStorage.removeItem('toba_current_user');
        }
      }
      
      if (savedToken) {
        setToken(savedToken);
        
        try {
          // Try to validate token with backend
          const result = await apiCall('/auth/validate', 'GET', null, savedToken);
          if (result.valid && result.user) {
            setUser(result.user);
            setToken(savedToken);
            setBackendAvailable(true);
            // Update localStorage dengan data terbaru dari backend
            localStorage.setItem('toba_current_user', JSON.stringify(result.user));
            logUserActivity(result.user.id, result.user.username, 'session_restored');
            console.log('✅ Token validated with backend:', result.user.username);
          } else {
            // Token invalid, clear storage
            console.log('❌ Token invalid, clearing...');
            localStorage.removeItem('toba_auth_token');
            localStorage.removeItem('toba_current_user');
            setUser(null);
            setToken(null);
          }
        } catch (error) {
          // Backend not available, keep the localStorage user
          console.log('⚠️ Backend not available, using localStorage user');
          // User sudah di-set dari localStorage di atas
        }
      } else {
        // Tidak ada token
        console.log('ℹ️ No saved token, user is guest');
        // Try to check if backend is available
        try {
          await apiCall('/status', 'GET');
          setBackendAvailable(true);
        } catch (error) {
          console.log('⚠️ Backend not available');
        }
      }
      
      setAllUsers(getStoredUsers());
      setAuthChecked(true); // Auth sudah selesai dicek
      setIsLoading(false);
      console.log('🔐 Auth initialization complete');
    };

    initAuth();
  }, []);

  const login = async (username, password) => {
    // Try backend first
    try {
      const result = await apiCall('/auth/login', 'POST', { username, password });
      
      if (result.success && result.token && result.user) {
        setUser(result.user);
        setToken(result.token);
        setBackendAvailable(true);
        localStorage.setItem('toba_auth_token', result.token);
        localStorage.setItem('toba_current_user', JSON.stringify(result.user));
        logUserActivity(result.user.id, result.user.username, 'login');
        return { success: true, role: result.user.role };
      }
    } catch (error) {
      console.log('Backend login failed, trying localStorage:', error.message);
    }
    
    // Fallback to localStorage authentication
    const users = getStoredUsers();
    const foundUser = users.find(
      (u) => u.username.toLowerCase() === username.toLowerCase() && u.password === password
    );

    if (foundUser) {
      const userData = {
        id: foundUser.id,
        username: foundUser.username,
        role: foundUser.role,
        name: foundUser.name,
        avatar: foundUser.avatar || '👤',
        email: foundUser.email || `${foundUser.username}@local`,
        loginTime: new Date().toISOString()
      };
      setUser(userData);
      localStorage.setItem('toba_current_user', JSON.stringify(userData));
      logUserActivity(foundUser.id, foundUser.username, 'login');
      return { success: true, role: foundUser.role };
    }

    return { success: false, message: 'Username atau password salah' };
  };

  // Handle OAuth callback - validate token from Google OAuth redirect
  const handleOAuthCallback = async (authToken) => {
    try {
      // Validate the token with backend
      const result = await apiCall('/auth/validate', 'GET', null, authToken);
      
      if (result.valid && result.user) {
        setUser(result.user);
        setToken(authToken);
        setBackendAvailable(true);
        localStorage.setItem('toba_auth_token', authToken);
        localStorage.setItem('toba_current_user', JSON.stringify(result.user));
        logUserActivity(result.user.id, result.user.username, 'login_google');
        return { success: true, role: result.user.role };
      }
      
      return { success: false, message: 'Token tidak valid' };
    } catch (error) {
      console.error('OAuth callback error:', error);
      return { success: false, message: error.message || 'Gagal validasi token' };
    }
  };

  // Get Google OAuth login URL
  const getGoogleLoginUrl = () => {
    const baseUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';
    return `${baseUrl}/api/auth/google/login`;
  };

  const register = async (username, password, name, email = null) => {
    // Try backend first
    try {
      const result = await apiCall('/auth/register', 'POST', { 
        username, 
        password, 
        name: name || username,
        email: email || `${username}@tobachatbot.local`
      });
      
      if (result.success && result.token && result.user) {
        setUser(result.user);
        setToken(result.token);
        setBackendAvailable(true);
        localStorage.setItem('toba_auth_token', result.token);
        localStorage.setItem('toba_current_user', JSON.stringify(result.user));
        return { success: true };
      }
    } catch (error) {
      console.log('Backend registration failed, trying localStorage:', error.message);
      // If error contains specific message, return it
      if (error.message && error.message !== 'API Error') {
        return { success: false, message: error.message };
      }
    }
    
    // Fallback to localStorage
    const users = getStoredUsers();
    
    // Check if username exists
    if (users.find(u => u.username.toLowerCase() === username.toLowerCase())) {
      return { success: false, message: 'Username sudah digunakan' };
    }

    // Generate new user
    const avatars = ['😊', '🙂', '😎', '🤓', '🧑', '👨', '👩', '🧔', '👱', '🙋'];
    const newUser = {
      id: Date.now(),
      username,
      password,
      name: name || username,
      email: email || `${username}@tobachatbot.local`,
      role: 'user',
      avatar: avatars[Math.floor(Math.random() * avatars.length)],
      createdAt: new Date().toISOString(),
      chatCount: 0,
      lastActive: new Date().toISOString()
    };

    users.push(newUser);
    saveUsersDB(users);
    setAllUsers(users);

    // Auto login after register
    const userData = {
      id: newUser.id,
      username: newUser.username,
      role: newUser.role,
      name: newUser.name,
      avatar: newUser.avatar,
      email: newUser.email,
      loginTime: new Date().toISOString()
    };
    setUser(userData);
    localStorage.setItem('toba_current_user', JSON.stringify(userData));
    logUserActivity(newUser.id, newUser.username, 'register');

    return { success: true };
  };

  const logout = async () => {
    if (user) {
      logUserActivity(user.id, user.username, 'logout');
    }
    
    // Try backend logout
    if (token) {
      try {
        await apiCall('/auth/logout', 'POST', null, token);
      } catch (error) {
        console.log('Backend logout error (ignored):', error);
      }
    }
    
    setUser(null);
    setToken(null);
    localStorage.removeItem('toba_auth_token');
    localStorage.removeItem('toba_current_user');
  };

  const updateUser = async (updates) => {
    // Try backend first
    if (token && backendAvailable) {
      try {
        const result = await apiCall('/user/profile', 'PUT', updates, token);
        if (result.success && result.user) {
          setUser(result.user);
          localStorage.setItem('toba_current_user', JSON.stringify(result.user));
          return { success: true, user: result.user };
        }
      } catch (error) {
        console.log('Backend update failed:', error.message);
      }
    }
    
    // Fallback to localStorage
    if (user) {
      const users = getStoredUsers();
      const idx = users.findIndex(u => u.id === user.id);
      if (idx !== -1) {
        users[idx] = { ...users[idx], ...updates };
        saveUsersDB(users);
      }
      
      const updatedUser = { ...user, ...updates };
      setUser(updatedUser);
      localStorage.setItem('toba_current_user', JSON.stringify(updatedUser));
      return { success: true, user: updatedUser };
    }
    
    return { success: false, message: 'User not logged in' };
  };

  const changePassword = async (oldPassword, newPassword) => {
    // Try backend first
    if (token && backendAvailable) {
      try {
        const result = await apiCall('/user/change-password', 'POST', {
          old_password: oldPassword,
          new_password: newPassword
        }, token);
        
        if (result.success) {
          // Logout user after password change
          logout();
          return { success: true, message: 'Password berhasil diubah. Silakan login kembali.' };
        }
      } catch (error) {
        return { success: false, message: error.message || 'Gagal mengubah password' };
      }
    }
    
    // Fallback to localStorage
    const users = getStoredUsers();
    const idx = users.findIndex(u => u.id === user?.id);
    if (idx !== -1) {
      if (users[idx].password !== oldPassword) {
        return { success: false, message: 'Password lama salah' };
      }
      users[idx].password = newPassword;
      saveUsersDB(users);
      return { success: true, message: 'Password berhasil diubah' };
    }
    
    return { success: false, message: 'User not found' };
  };

  const getUserChatHistory = async () => {
    // Try backend first
    if (token && backendAvailable) {
      try {
        const result = await apiCall('/user/history', 'GET', null, token);
        return result.history || [];
      } catch (error) {
        console.log('Backend history fetch failed:', error);
      }
    }
    
    // Fallback to localStorage
    try {
      const history = JSON.parse(localStorage.getItem('toba_chat_history') || '[]');
      return history.filter(h => h.userId === user?.id);
    } catch (e) {
      return [];
    }
  };

  const clearChatHistory = async () => {
    // Try backend first
    if (token && backendAvailable) {
      try {
        await apiCall('/user/history', 'DELETE', null, token);
        return true;
      } catch (error) {
        console.log('Backend clear history failed:', error);
      }
    }
    
    // Fallback to localStorage
    try {
      const history = JSON.parse(localStorage.getItem('toba_chat_history') || '[]');
      const filtered = history.filter(h => h.userId !== user?.id);
      localStorage.setItem('toba_chat_history', JSON.stringify(filtered));
      return true;
    } catch (e) {
      return false;
    }
  };

  const updateUserStats = (action, details = {}) => {
    if (!user) return;
    
    const users = getStoredUsers();
    const idx = users.findIndex(u => u.id === user.id);
    if (idx !== -1) {
      users[idx].lastActive = new Date().toISOString();
      if (action === 'chat') {
        users[idx].chatCount = (users[idx].chatCount || 0) + 1;
      }
      saveUsersDB(users);
    }
    logUserActivity(user.id, user.username, action, details);
  };

  const getAllUsers = async () => {
    // Try backend first (admin only)
    if (token && backendAvailable && user?.role === 'admin') {
      try {
        const result = await apiCall('/admin/users', 'GET', null, token);
        return result.users || [];
      } catch (error) {
        console.log('Backend get users failed:', error);
      }
    }
    
    return getStoredUsers().filter(u => u.role === 'user');
  };

  const getSystemStats = async () => {
    // Try backend first (admin only)
    if (token && backendAvailable && user?.role === 'admin') {
      try {
        const result = await apiCall('/admin/stats', 'GET', null, token);
        return result;
      } catch (error) {
        console.log('Backend get stats failed:', error);
      }
    }
    
    // Fallback stats
    const users = getStoredUsers();
    const logs = JSON.parse(localStorage.getItem('toba_user_activity') || '[]');
    return {
      stats: {
        totalUsers: users.filter(u => u.role === 'user').length,
        totalChats: users.reduce((sum, u) => sum + (u.chatCount || 0), 0),
        activeSessions: 1
      }
    };
  };

  const getUserActivity = (limit = 100) => {
    try {
      const logs = JSON.parse(localStorage.getItem('toba_user_activity') || '[]');
      return logs.slice(0, limit);
    } catch (e) {
      return [];
    }
  };

  const isAdmin = () => user?.role === 'admin';
  const isOperator = () => user?.role === 'operator';
  const isUser = () => user?.role === 'user';

  return (
    <AuthContext.Provider value={{ 
      user, 
      token,
      login,
      handleOAuthCallback,
      getGoogleLoginUrl,
      register,
      logout,
      updateUser,
      changePassword,
      getUserChatHistory,
      clearChatHistory,
      isLoading,
      authChecked, // Flag untuk memastikan auth sudah dicek
      isAuthenticated: !!user,
      isAdmin,
      isOperator,
      isUser,
      updateUserStats,
      getAllUsers,
      getSystemStats,
      getUserActivity,
      backendAvailable
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
