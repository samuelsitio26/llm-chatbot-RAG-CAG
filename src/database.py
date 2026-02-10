"""
SQLite Database Manager for Toba Tourism Chatbot
Handles user management, chat history, and session management
"""

import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import os

# Database path
DB_DIR = Path(__file__).parent.parent / "database"
DB_PATH = DB_DIR / "toba_chatbot.db"

def get_db_connection():
    """Create a database connection with row factory"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with all required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            avatar TEXT DEFAULT '😊',
            role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'operator', 'user')),
            bio TEXT,
            location TEXT,
            favorite_categories TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Sessions table for authentication tokens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            response_time_ms INTEGER,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    
    # Activity log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    
    # User preferences/settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme TEXT DEFAULT 'dark',
            language TEXT DEFAULT 'id',
            notification_enabled INTEGER DEFAULT 1,
            email_updates INTEGER DEFAULT 0,
            preferences_json TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (chat_id) REFERENCES chat_history(id) ON DELETE CASCADE
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)')
    
    conn.commit()
    
    # Create default admin user if not exists
    create_default_admin(cursor, conn)
    
    conn.close()
    print(f"✅ Database initialized at: {DB_PATH}")

def create_default_admin(cursor, conn):
    """Create default admin user if not exists"""
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        password_hash = hash_password("Admin#123")
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name, avatar, role, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin@tobachatbot', password_hash, 'Administrator', '👨‍💼', 'admin', 'System Administrator'))
        conn.commit()
        print("✅ Default admin user created (email: admin@tobachatbot, password: Admin#123)")

def hash_password(password: str, salt: str = None) -> str:
    """Hash password with salt using SHA-256"""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}${hash_obj.hexdigest()}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    try:
        salt, stored_hash = password_hash.split('$')
        new_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return new_hash == stored_hash
    except:
        return False

def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

# ============================================
# User Management Functions
# ============================================

def create_user(username: str, email: str, password: str, name: str = None, 
                role: str = 'user', avatar: str = '😊') -> Dict[str, Any]:
    """Create a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if username or email exists
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            return {"success": False, "error": "Username atau email sudah terdaftar"}
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name, avatar, role)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, name or username, avatar, role))
        
        user_id = cursor.lastrowid
        
        # Create default preferences
        cursor.execute('''
            INSERT INTO user_preferences (user_id) VALUES (?)
        ''', (user_id,))
        
        conn.commit()
        
        # Log activity
        log_activity(user_id, "register", "User registered successfully")
        
        return {
            "success": True,
            "user_id": user_id,
            "message": "Registrasi berhasil"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def authenticate_user(username: str, password: str, ip_address: str = None, 
                     user_agent: str = None) -> Dict[str, Any]:
    """Authenticate user and create session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, password_hash, name, avatar, role, bio, location, 
                   favorite_categories, is_active, created_at
            FROM users WHERE username = ? OR email = ?
        ''', (username, username))
        
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "Username tidak ditemukan"}
        
        if not user['is_active']:
            return {"success": False, "error": "Akun telah dinonaktifkan"}
        
        if not verify_password(password, user['password_hash']):
            log_activity(user['id'], "login_failed", "Invalid password attempt", ip_address)
            return {"success": False, "error": "Password salah"}
        
        # Create session token
        token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user['id'], token, expires_at, ip_address, user_agent))
        
        # Update last login
        cursor.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user['id'],))
        
        conn.commit()
        
        # Log activity
        log_activity(user['id'], "login", "User logged in successfully", ip_address)
        
        # Parse favorite_categories
        favorite_categories = []
        try:
            favorite_categories = json.loads(user['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "name": user['name'],
                "avatar": user['avatar'],
                "role": user['role'],
                "bio": user['bio'],
                "location": user['location'],
                "favoriteCategories": favorite_categories,
                "createdAt": user['created_at']
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate session token and return user data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT s.user_id, s.expires_at, u.id, u.username, u.email, u.name, 
                   u.avatar, u.role, u.bio, u.location, u.favorite_categories, u.is_active
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        ''', (token,))
        
        result = cursor.fetchone()
        
        if not result:
            return None
        
        # Check if expired
        expires_at = datetime.fromisoformat(result['expires_at'])
        if expires_at < datetime.now():
            # Delete expired session
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        
        if not result['is_active']:
            return None
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(result['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "id": result['id'],
            "username": result['username'],
            "email": result['email'],
            "name": result['name'],
            "avatar": result['avatar'],
            "role": result['role'],
            "bio": result['bio'],
            "location": result['location'],
            "favoriteCategories": favorite_categories
        }
    except Exception as e:
        print(f"Session validation error: {e}")
        return None
    finally:
        conn.close()

def logout_user(token: str) -> bool:
    """Invalidate user session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user_id before deleting
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        session = cursor.fetchone()
        
        if session:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            log_activity(session['user_id'], "logout", "User logged out")
        
        return True
    except:
        return False
    finally:
        conn.close()


def get_or_create_google_user(email: str, name: str = None, avatar: str = None,
                               ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
    """
    Get or create a user from Google OAuth login.
    If user exists by email, log them in.
    If not, create new user and log them in.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists by email
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, is_active, created_at
            FROM users WHERE email = ?
        ''', (email,))
        
        user = cursor.fetchone()
        
        if user:
            # User exists
            if not user['is_active']:
                return {"success": False, "error": "Akun telah dinonaktifkan"}
            
            user_id = user['id']
            
            # Update name/avatar if provided and different
            updates = []
            values = []
            if name and name != user['name']:
                updates.append("name = ?")
                values.append(name)
            if avatar and avatar != user['avatar']:
                updates.append("avatar = ?")
                values.append(avatar)
            
            if updates:
                values.append(user_id)
                cursor.execute(f'''
                    UPDATE users SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', values)
                conn.commit()
        else:
            # Create new user
            # Generate username from email (before @)
            base_username = email.split('@')[0]
            username = base_username
            suffix = 1
            
            # Ensure unique username
            while True:
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if not cursor.fetchone():
                    break
                username = f"{base_username}{suffix}"
                suffix += 1
            
            # Create random password (user won't use it, they login via Google)
            random_password = secrets.token_urlsafe(32)
            password_hash = hash_password(random_password)
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, name, avatar, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, name or username, avatar or '😊', 'user'))
            
            user_id = cursor.lastrowid
            
            # Create default preferences
            cursor.execute('INSERT INTO user_preferences (user_id) VALUES (?)', (user_id,))
            conn.commit()
            
            log_activity(user_id, "register_google", "User registered via Google OAuth", ip_address)
        
        # Create session token
        token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, token, expires_at, ip_address, user_agent))
        
        # Update last login
        cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()
        
        # Fetch updated user data
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, created_at
            FROM users WHERE id = ?
        ''', (user_id,))
        
        u = cursor.fetchone()
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(u['favorite_categories'] or '[]')
        except:
            pass
        
        log_activity(user_id, "login_google", "User logged in via Google OAuth", ip_address)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": u['id'],
                "username": u['username'],
                "email": u['email'],
                "name": u['name'],
                "avatar": u['avatar'],
                "role": u['role'],
                "bio": u['bio'],
                "location": u['location'],
                "favoriteCategories": favorite_categories,
                "createdAt": u['created_at']
            }
        }
    except Exception as e:
        print(f"Google OAuth error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def update_user(user_id: int, **kwargs) -> Dict[str, Any]:
    """Update user profile"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    allowed_fields = ['name', 'avatar', 'bio', 'location', 'favorite_categories']
    update_fields = []
    values = []
    
    for field in allowed_fields:
        if field in kwargs:
            value = kwargs[field]
            if field == 'favorite_categories' and isinstance(value, list):
                value = json.dumps(value)
            update_fields.append(f"{field} = ?")
            values.append(value)
    
    if not update_fields:
        return {"success": False, "error": "No fields to update"}
    
    values.append(user_id)
    
    try:
        cursor.execute(f'''
            UPDATE users SET {", ".join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        conn.commit()
        
        log_activity(user_id, "profile_update", f"Updated fields: {', '.join(update_fields)}")
        
        return {"success": True, "message": "Profile updated successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def change_password(user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
    """Change user password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "User not found"}
        
        if not verify_password(old_password, user['password_hash']):
            return {"success": False, "error": "Password lama salah"}
        
        new_hash = hash_password(new_password)
        cursor.execute('''
            UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (new_hash, user_id))
        
        # Invalidate all sessions except current
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        
        conn.commit()
        
        log_activity(user_id, "password_change", "Password changed successfully")
        
        return {"success": True, "message": "Password berhasil diubah"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, created_at, last_login, is_active
            FROM users WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return None
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(user['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "name": user['name'],
            "avatar": user['avatar'],
            "role": user['role'],
            "bio": user['bio'],
            "location": user['location'],
            "favoriteCategories": favorite_categories,
            "createdAt": user['created_at'],
            "lastLogin": user['last_login'],
            "isActive": bool(user['is_active'])
        }
    except:
        return None
    finally:
        conn.close()

def get_all_users(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all users (admin function)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = '''
            SELECT id, username, email, name, avatar, role, bio, location,
                   created_at, last_login, is_active
            FROM users
        '''
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query)
        users = cursor.fetchall()
        
        return [
            {
                "id": u['id'],
                "username": u['username'],
                "email": u['email'],
                "name": u['name'],
                "avatar": u['avatar'],
                "role": u['role'],
                "bio": u['bio'],
                "location": u['location'],
                "createdAt": u['created_at'],
                "lastLogin": u['last_login'],
                "isActive": bool(u['is_active'])
            }
            for u in users
        ]
    except:
        return []
    finally:
        conn.close()

def delete_user(user_id: int, admin_id: int) -> Dict[str, Any]:
    """Delete (deactivate) user account"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if trying to delete self as admin
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Soft delete - just deactivate
        cursor.execute('''
            UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user_id,))
        
        # Delete all sessions
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        
        conn.commit()
        
        log_activity(admin_id, "user_deactivate", f"Deactivated user ID: {user_id}")
        
        return {"success": True, "message": "User account deactivated"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

# ============================================
# Chat History Functions
# ============================================

def save_chat(user_id: Optional[int], session_id: str, question: str, answer: str,
              category: str = None, response_time_ms: int = None, 
              model_used: str = None) -> int:
    """Save chat to history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO chat_history 
            (user_id, session_id, question, answer, category, response_time_ms, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, question, answer, category, response_time_ms, model_used))
        
        conn.commit()
        return cursor.lastrowid
    except:
        return -1
    finally:
        conn.close()

def get_user_chat_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get chat history for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, question, answer, category, response_time_ms, model_used, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        chats = cursor.fetchall()
        
        return [
            {
                "id": c['id'],
                "question": c['question'],
                "answer": c['answer'],
                "category": c['category'],
                "responseTime": c['response_time_ms'],
                "modelUsed": c['model_used'],
                "timestamp": c['created_at']
            }
            for c in chats
        ]
    except:
        return []
    finally:
        conn.close()

def get_session_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Get chat history for a session (for guests)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, question, answer, category, created_at
            FROM chat_history
            WHERE session_id = ?
            ORDER BY created_at ASC
        ''', (session_id,))
        
        return [dict(c) for c in cursor.fetchall()]
    except:
        return []
    finally:
        conn.close()

def clear_user_chat_history(user_id: int) -> bool:
    """Clear all chat history for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        conn.commit()
        log_activity(user_id, "clear_history", "User cleared chat history")
        return True
    except:
        return False
    finally:
        conn.close()

# ============================================
# Activity Log Functions
# ============================================

def log_activity(user_id: int, action: str, details: str = None, 
                ip_address: str = None) -> None:
    """Log user activity"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO activity_log (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, details, ip_address))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def get_user_activity(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get activity log for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT action, details, ip_address, created_at
            FROM activity_log
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        return [dict(a) for a in cursor.fetchall()]
    except:
        return []
    finally:
        conn.close()

def get_system_stats() -> Dict[str, Any]:
    """Get system statistics (admin function)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1")
        total_users = cursor.fetchone()['count']
        
        # Users by role
        cursor.execute('''
            SELECT role, COUNT(*) as count FROM users 
            WHERE is_active = 1 GROUP BY role
        ''')
        users_by_role = {r['role']: r['count'] for r in cursor.fetchall()}
        
        # Total chats
        cursor.execute("SELECT COUNT(*) as count FROM chat_history")
        total_chats = cursor.fetchone()['count']
        
        # Chats today
        cursor.execute('''
            SELECT COUNT(*) as count FROM chat_history 
            WHERE DATE(created_at) = DATE('now')
        ''')
        chats_today = cursor.fetchone()['count']
        
        # Active sessions
        cursor.execute('''
            SELECT COUNT(*) as count FROM sessions 
            WHERE expires_at > CURRENT_TIMESTAMP
        ''')
        active_sessions = cursor.fetchone()['count']
        
        # Recent registrations (last 7 days)
        cursor.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE created_at > datetime('now', '-7 days')
        ''')
        recent_registrations = cursor.fetchone()['count']
        
        return {
            "totalUsers": total_users,
            "usersByRole": users_by_role,
            "totalChats": total_chats,
            "chatsToday": chats_today,
            "activeSessions": active_sessions,
            "recentRegistrations": recent_registrations
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

# ============================================
# Feedback Functions
# ============================================

def save_feedback(user_id: Optional[int], chat_id: int, rating: int, 
                 comment: str = None) -> bool:
    """Save feedback for a chat response"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO feedback (user_id, chat_id, rating, comment)
            VALUES (?, ?, ?, ?)
        ''', (user_id, chat_id, rating, comment))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT AVG(rating) as avg, COUNT(*) as count FROM feedback")
        result = cursor.fetchone()
        
        cursor.execute('''
            SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating ORDER BY rating
        ''')
        distribution = {r['rating']: r['count'] for r in cursor.fetchall()}
        
        return {
            "averageRating": round(result['avg'] or 0, 2),
            "totalFeedback": result['count'],
            "distribution": distribution
        }
    except:
        return {"averageRating": 0, "totalFeedback": 0, "distribution": {}}
    finally:
        conn.close()

# ============================================
# Cleanup Functions
# ============================================

def cleanup_expired_sessions():
    """Remove expired sessions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except:
        return 0
    finally:
        conn.close()

# Initialize database when module is imported
if __name__ == "__main__":
    init_database()
    print("Database setup complete!")
    
    # Show stats
    stats = get_system_stats()
    print(f"\nSystem Stats:")
    print(f"  Total Users: {stats.get('totalUsers', 0)}")
    print(f"  Total Chats: {stats.get('totalChats', 0)}")
