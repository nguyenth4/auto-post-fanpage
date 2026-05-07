## Auto Post Fanpage / Multi-Platform Connections

App Flask hỗ trợ:

- **Đăng ký/đăng nhập**: email + password, hoặc **Google OAuth**
- **Kết nối đa nền tảng**: Facebook Page (Meta), TikTok, YouTube (Google)
- **Multi-account**: lưu nhiều Page/Channel/Account cho mỗi user
- **Trạng thái**: `connected / expired / error / disconnected`
- **Tự refresh token**: Google/YouTube + TikTok (Facebook Page thường cần reconnect)

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy local

```bash
python app.py
```

Mặc định chạy `http://127.0.0.1:5000`.

## Biến môi trường (.env)

Tối thiểu:

- **SECRET_KEY**: chuỗi random dài
- **DATABASE_URL** (khuyến nghị): Postgres (ví dụ Supabase) để chạy production ổn định  
  Nếu không có, app dùng `sqlite:///app.db` (chỉ phù hợp local).

OAuth:

- **GOOGLE_CLIENT_ID**, **GOOGLE_CLIENT_SECRET**
- **FACEBOOK_CLIENT_ID**, **FACEBOOK_CLIENT_SECRET**
- **TIKTOK_CLIENT_KEY**, **TIKTOK_CLIENT_SECRET**

Cookie (khuyến nghị production):

- **SESSION_COOKIE_SECURE**: `true`
- **SESSION_COOKIE_SAMESITE**: `Lax` (hoặc `None` nếu cần embed/3rd-party)

## Redirect URL cần cấu hình

Khi deploy (ví dụ Vercel), thay `BASE_URL` bằng domain thật.

### Google OAuth

- Authorized redirect URI:  
  `BASE_URL/auth/google/callback`

Scope đã bật sẵn: `openid email profile` và `youtube.readonly`.

### Facebook (Meta)

- Valid OAuth Redirect URI:  
  `BASE_URL/connect/facebook/callback`

App dùng scope: `pages_show_list,pages_read_engagement,pages_manage_posts`

### TikTok

- Redirect URI:  
  `BASE_URL/connect/tiktok/callback`

## Ghi chú

- **Facebook Page**: app sẽ lấy danh sách page qua `/me/accounts` và lưu từng page như một connection.
- **Refresh token**: nút “Refresh token” gọi `/api/connections/refresh` để refresh các connection đang `expired`.