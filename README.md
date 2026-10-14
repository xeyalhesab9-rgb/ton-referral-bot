
# TON Referral Bot

Telegram üçün TON referal və mükafat botu.

## Funksiyalar

- Telegram referal linkləri
- Hər təsdiqlənmiş referala 0.01 TON
- İstifadəçi balansı
- Minimum çıxarış: 0.1 TON
- Admin təsdiqli çıxarış
- Supabase PostgreSQL bazası
- Vercel Telegram Webhook

## Texnologiyalar

- Python
- Flask
- PostgreSQL
- Supabase
- Vercel
- Telegram Bot API

## Vercel Environment Variables

BOT_TOKEN
BOT_USERNAME
ADMIN_ID
DATABASE_URL
WEBHOOK_SECRET

Bütün gizli məlumatlar Vercel Environment
Variables bölməsində saxlanmalıdır.

## Admin əmrləri

/approve_ref USER_ID
/paid ID
/reject ID

## Çıxarış

İstifadəçi bu əmri göndərir:

/withdraw TON_WALLET_ADDRESS

Minimum çıxarış 0.1 TON-dur.

## Təhlükəsizlik

Real TON ödənişləri avtomatik edilmir.
Admin ödənişi əl ilə göndərir.

Bot real istifadəyə verilməzdən əvvəl
təhlükəsizlik yoxlamaları tamamlanmalıdır.
