# Google Imagen & Gemini — Available Models

## Recommended: Imagen 3

| Model Name | API Type | Chất lượng | Tốc độ | Ghi chú |
|---|---|---|---|---|
| `imagen-3.0-generate-002` | `predict` | ⭐⭐⭐⭐⭐ | Trung bình | Mặc định, chất lượng cao nhất |

**Endpoint:** `POST .../v1beta/models/imagen-3.0-generate-002:predict`

**Payload format (Imagen):**
```json
{
  "instances": [{"prompt": "your prompt"}],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "16:9",
    "outputOptions": {"mimeType": "image/png"}
  }
}
```

---

## Gemini Models (Experimental Image Generation)

| Model Name | API Type | Ghi chú |
|---|---|---|
| `gemini-2.0-flash-exp` | `generateContent` | Hỗ trợ tạo ảnh inline |

**Lưu ý:** Gemini models dùng endpoint `generateContent` với `inlineData` response. Cần kiểm tra xem model có hỗ trợ image output không tại thời điểm dùng.

---

## Aspect Ratios Hợp Lệ

| Ratio | Dùng cho |
|---|---|
| `1:1` | Square — Instagram, avatar |
| `16:9` | Widescreen — banner, wallpaper, YouTube thumbnail |
| `9:16` | Portrait — Story, TikTok, mobile |
| `4:3` | Classic — presentation, blog |
| `3:4` | Tall portrait |

---

## Lấy API Key

1. Truy cập https://aistudio.google.com/app/apikey
2. Đăng nhập Google Account
3. Click "Create API Key"
4. Copy key vào `.env` file:
   ```
   GEMINI_API_KEY=your_key_here
   ```

**Quota miễn phí:** Imagen 3 có quota free tier. Xem tại https://ai.google.dev/pricing
