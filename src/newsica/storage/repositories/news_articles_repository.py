import time
from newsica.storage.database import get_connection

def save_articles(articles: list[dict], category: str = "news", is_breaking: bool = False):
    """
    Salva una lista di articoli nel database.
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    is_break = 1 if is_breaking else 0
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            for article in articles:
                # Usa l'URL come ID o generane uno. Per le news di NewsAPI di solito url è unico.
                article_id = article.get("url") or article.get("title")
                title = article.get("title", "")
                content = article.get("description", "") or article.get("content", "")
                published_at = article.get("publishedAt", now)
                
                cursor.execute('''
                    INSERT INTO news_articles (id, title, content, category, published_at, is_breaking)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        content=excluded.content,
                        is_breaking=excluded.is_breaking
                ''', (article_id, title, content, category, published_at, is_break))
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ Errore db in save_articles: {e}")
        return False

def get_recent_articles(category: str = "news", limit: int = 15):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, content as description, published_at as publishedAt, is_breaking
                FROM news_articles 
                WHERE category = ?
                ORDER BY published_at DESC LIMIT ?
            ''', (category, limit))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_recent_articles: {e}")
        return []
