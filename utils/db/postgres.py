from typing import Union
import asyncpg
from asyncpg import Connection
from asyncpg.pool import Pool
from data import config


class Database:
    def __init__(self):
        self.pool: Union[Pool, None] = None

    async def create(self):
        self.pool = await asyncpg.create_pool(
            user=config.DB_USER,
            password=config.DB_PASS,
            host=config.DB_HOST,
            port=int(config.DB_PORT),
            database=config.DB_NAME,
        )

    async def execute(self, command, *args, fetch=False, fetchval=False, fetchrow=False, execute=False):
        async with self.pool.acquire() as connection:
            connection: Connection
            async with connection.transaction():
                if fetch:
                    result = await connection.fetch(command, *args)
                elif fetchval:
                    result = await connection.fetchval(command, *args)
                elif fetchrow:
                    result = await connection.fetchrow(command, *args)
                elif execute:
                    result = await connection.execute(command, *args)
            return result

    # ===================== JADVALLAR YARATISH =====================

    async def create_tables(self):
        await self.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tg_id BIGINT NOT NULL UNIQUE,
            fullname VARCHAR(255),
            username VARCHAR(255),
            phone VARCHAR(30),
            created_at TIMESTAMP DEFAULT NOW()
        );
        """, execute=True)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            channel_id BIGINT NOT NULL UNIQUE,
            url VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
        """, execute=True)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            platform VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            tg_file_id VARCHAR(255),
            error_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """, execute=True)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,
            screenshot_file_id VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """, execute=True)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL
        );
        """, execute=True)

        await self.execute("""
        INSERT INTO settings (key, value) VALUES
            ('payment_card', $1),
            ('payment_owner', $2),
            ('doc_price', $3),
            ('payment_enabled', '0')
        ON CONFLICT (key) DO NOTHING;
        """, config.PAYMENT_CARD, config.PAYMENT_OWNER, str(config.DOC_PRICE), execute=True)

        await self.execute("""
        INSERT INTO settings (key, value) VALUES
            ('start_text', $1),
            ('help_text', $2)
        ON CONFLICT (key) DO NOTHING;
        """,
        "Assalomu alaykum, {name}! 👋\n\n"
        "Men <b>video yuklab beruvchi bot</b>man.\n\n"
        "Menga Instagram, YouTube, TikTok yoki boshqa platformadan video havolasini yuboring — "
        "men uni siz uchun yuklab beraman. 🎬",
        "📌 <b>Yordam</b>\n\n"
        "Botdan foydalanish juda oson:\n"
        "1. Instagram, YouTube yoki TikTok'dan video havolasini nusxalang\n"
        "2. Havolani shu botga yuboring\n"
        "3. Bot videoni yuklab beradi\n\n"
        "Qo'llab-quvvatlanadigan platformalar:\n"
        "• YouTube (video va Shorts)\n"
        "• Instagram (Reels, post, IGTV)\n"
        "• TikTok\n"
        "• Va boshqa 1000+ saytlar\n\n"
        "Muammo bo'lsa admin bilan bog'laning.",
        execute=True)

    # ===================== USERS =====================

    async def add_user(self, tg_id: int, fullname: str, username=None):
        sql = """
        INSERT INTO users (tg_id, fullname, username)
        VALUES ($1, $2, $3)
        ON CONFLICT (tg_id) DO UPDATE SET fullname=$2, username=$3
        RETURNING *
        """
        return await self.execute(sql, tg_id, fullname, username, fetchrow=True)

    async def get_user(self, tg_id: int):
        return await self.execute("SELECT * FROM users WHERE tg_id=$1", tg_id, fetchrow=True)

    async def get_all_users(self):
        return await self.execute("SELECT * FROM users ORDER BY created_at DESC", fetch=True)

    async def count_users(self) -> int:
        return await self.execute("SELECT COUNT(*) FROM users", fetchval=True)

    # ===================== CHANNELS =====================

    async def add_channel(self, channel_id: int, url: str, name: str):
        sql = """
        INSERT INTO channels (channel_id, url, name)
        VALUES ($1, $2, $3)
        ON CONFLICT (channel_id) DO UPDATE SET url=$2, name=$3, is_active=TRUE
        RETURNING *
        """
        return await self.execute(sql, channel_id, url, name, fetchrow=True)

    async def get_active_channels(self):
        return await self.execute("SELECT * FROM channels WHERE is_active=TRUE", fetch=True)

    async def get_all_channels(self):
        return await self.execute("SELECT * FROM channels", fetch=True)

    async def delete_channel(self, channel_id: int):
        await self.execute("DELETE FROM channels WHERE channel_id=$1", channel_id, execute=True)

    # ===================== DOWNLOADS =====================

    async def create_download(self, user_id: int, url: str, platform: str = None):
        sql = """
        INSERT INTO downloads (user_id, url, platform, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING *
        """
        return await self.execute(sql, user_id, url, platform, fetchrow=True)

    async def update_download_status(self, dl_id: int, status: str, tg_file_id: str = None, error_text: str = None):
        await self.execute(
            "UPDATE downloads SET status=$1, tg_file_id=$2, error_text=$3 WHERE id=$4",
            status, tg_file_id, error_text, dl_id, execute=True
        )

    async def count_today_downloads(self) -> int:
        return await self.execute(
            "SELECT COUNT(*) FROM downloads WHERE status='success' AND created_at::date = CURRENT_DATE",
            fetchval=True
        )

    async def count_total_downloads(self) -> int:
        return await self.execute(
            "SELECT COUNT(*) FROM downloads WHERE status='success'",
            fetchval=True
        )

    # ===================== PAYMENTS =====================

    async def count_today_payments(self) -> int:
        return await self.execute(
            "SELECT COUNT(*) FROM payments WHERE status='approved' AND created_at::date = CURRENT_DATE",
            fetchval=True
        )

    async def sum_today_payments(self) -> int:
        result = await self.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='approved' AND created_at::date = CURRENT_DATE",
            fetchval=True
        )
        return int(result)

    async def sum_all_payments(self) -> int:
        result = await self.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='approved'",
            fetchval=True
        )
        return int(result)

    # ===================== SETTINGS =====================

    async def get_setting(self, key: str):
        result = await self.execute("SELECT value FROM settings WHERE key=$1", key, fetchrow=True)
        return result['value'] if result else None

    async def set_setting(self, key: str, value: str):
        await self.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value=$2",
            key, value, execute=True
        )

    async def get_payment_info(self) -> dict:
        card = await self.get_setting('payment_card')
        owner = await self.get_setting('payment_owner')
        price = await self.get_setting('doc_price')
        return {
            'card': card or config.PAYMENT_CARD,
            'owner': owner or config.PAYMENT_OWNER,
            'price': int(price) if price else config.DOC_PRICE,
        }
