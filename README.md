# Discord to Telegram Forwarder Bot

Bot yang memungkinkan penerusan (forwarding) pesan dari channel Discord ke channel/supergroup Telegram dengan dukungan untuk topics.

## Fitur

- Forward pesan dari Discord ke Telegram
- Kirim foto/gambar langsung, bukan hanya URL
- Dukungan untuk embed Discord (title, description, fields, dll)
- Support pesan dari bot dan webhook Discord
- Konfigurasi menggunakan command Discord
- Dukungan untuk supergroup dan topics di Telegram
- Database SQLite untuk konfigurasi yang persisten
- Penanganan kesalahan yang robust
- Setup dan manajemen yang mudah

## Setup

1. Clone repository ini
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Buat file `.env` dengan format:
   ```
   # Discord Bot Token (dari https://discord.com/developers/applications)
   DISCORD_TOKEN=your_discord_bot_token_here

   # Telegram Bot Token (dari @BotFather)
   TELEGRAM_TOKEN=your_telegram_bot_token_here

   # Database Configuration
   DATABASE_PATH=config/bot_config.db
   ```
4. Jalankan bot:
   ```
   python src/main.py
   ```

## Discord Commands

- `!forward setup <telegram_chat_id> [topic_id]` - Setup forwarding dari channel Discord saat ini
- `!forward setup @https://t.me/c/{chat_id}/{topic_id}` - Setup menggunakan URL Telegram (direkomendasikan)
- `!forward list` - Tampilkan semua aturan forwarding yang aktif
- `!forward remove` - Hapus forwarding dari channel Discord saat ini
- `!forward help` - Tampilkan informasi bantuan

## Konfigurasi

### Menggunakan URL Telegram (Direkomendasikan)

Cara termudah untuk setup forwarding adalah menggunakan URL Telegram:

1. Tambahkan bot ke grup/channel Telegram target
2. Kirim pesan di grup atau topic
3. Klik kanan pada pesan dan pilih "Copy Link"
4. Di Discord, jalankan `!forward setup @<paste_link_yang_dicopy>`

Contoh: `!forward setup @https://t.me/c/1234567890/123`

### Menggunakan Chat ID dan Topic ID Secara Manual

Alternatif, konfigurasi dapat dilakukan menggunakan ID secara langsung:

1. Tambahkan bot ke channel/supergroup
2. Kirim pesan ke channel
3. Kunjungi `https://api.telegram.org/bot<TOKEN_BOT_ANDA>/getUpdates`
4. Cari objek `chat` untuk menemukan `chat_id`

Untuk topic ID di supergroup:
1. Kirim pesan ke topic
2. Periksa `message_thread_id` di API response di atas

## Format Pesan yang Diteruskan

Bot akan meneruskan:
- Teks pesan
- Embed (judul, deskripsi, fields, dll)
- Gambar (dikirim sebagai foto di Telegram)
- Attachment lainnya (dikirim sebagai URL)

Pesan diteruskan tanpa menyertakan nama pengirim asli dari Discord. 