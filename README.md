# Office Attendance System (QR + PIN + Location)

Yeh ek chota web-app hai jo biometric machine ki jagah kaam karta hai:
- Employee deewar par laga QR code apne phone se scan karta hai
- Apna naam list se chunta hai aur apna PIN dalta hai (biometric ki jagah identity confirm karne ke liye)
- Check In / Check Out button dabata hai
- App automatically time, date, aur GPS location save kar leta hai
- 10:15 AM ke baad check-in "Late" mark hota hai
- Sunday ko check-in band rehta hai (holiday)
- Owners (Hunain, Hammad, Fahad) ke liye alag Admin Dashboard hai jahan sab ka record, monthly report aur CSV download mil jata hai

## Employees already add kiye hue hain

**Owners:** Hunain Khan, Hammad Ahmed, Fahad Ahmed
**Employees:** Arham Zafar, Zaim, Maaz, Sinan, Hassan Khan, Abdullah, Rehan, Ahsan, Huzaifa, Hassan

Har employee ka ek starting PIN set hai (0000 se shuru na ho isliye 1000s/2000s use kiye):
- Owners: 1000, 1001, 1002 (Hunain, Hammad, Fahad, isi order mein)
- Employees: 2000 se 2009 tak, upar diye gaye order mein (Arham=2000, Zaim=2001, Maaz=2002, Sinan=2003, Hassan Khan=2004, Abdullah=2005, Rehan=2006, Ahsan=2007, Huzaifa=2008, Hassan=2009)

**Zaruri:** App chalate hi Admin Dashboard > Employees page se sab ke PIN apni pasand ke 4-digit number se change kar dein, taake koi dusra guess na kar sake.

## Settings jo aap badal sakte hain (app.py ke shuru mein)

```python
ADMIN_PASSWORD = "office786"      # Admin dashboard ka password - zaroor badlein
LATE_TIME = time(10, 15)          # Is time ke baad check-in = Late
OFFICE_CLOSE_TIME = time(19, 0)   # Office band hone ka time (7:00 PM)
SUNDAY_IS_HOLIDAY = True          # Sunday ko check-in band

OFFICE_LAT = None                 # Apne office ki latitude (Google Maps se milegi)
OFFICE_LNG = None                 # Apne office ki longitude
OFFICE_RADIUS_M = 150             # Kitne meter ke andar se check-in allowed ho (geofence)
```

Agar aap chahte hain ke koi office ke bahar se check-in na kar sake, to `OFFICE_LAT` aur `OFFICE_LNG` apne office ki coordinates se fill kar dein (Google Maps par apni location par right-click karke coordinates copy kar sakte hain).

---

## Step 1: Computer par test karna (optional, dekhne ke liye)

```bash
pip install -r requirements.txt
python app.py
```

Phir browser mein kholein: `http://localhost:5000/checkin`
Admin: `http://localhost:5000/admin`

---

## Step 2: FREE hosting par daalna (taake QR code hamesha kaam kare)

App ko internet par daalne ke liye **Render.com** ka free plan sabse aasan hai. Steps:

1. [render.com](https://render.com) par free account banayein (GitHub se sign-up kar sakte hain).
2. Is poore folder (`attendance_app`) ko GitHub par ek naya repository bana kar upload karein.
   - GitHub.com par "New repository" > files upload karein, ya `git init`, `git add .`, `git commit`, `git push` use karein.
3. Render dashboard mein **"New +" > "Web Service"** par click karein aur apni GitHub repo select karein.
4. Yeh settings dalein:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Environment Variables mein (optional lekin recommended):
   - `ADMIN_PASSWORD` = apna khud ka strong password
   - `SECRET_KEY` = koi bhi random lamba text
6. "Create Web Service" dabayein. 2-3 minute mein aapko ek URL milega jaisे:
   `https://office-attendance-xxxx.onrender.com`

**Note:** Render ke free plan par agar app 15 minute tak use na ho to so jata hai aur agli request par 20-30 second mein wake ho jata hai — office ke liye yeh normally koi masla nahi.

Database (`attendance.db`) free plan par restart hone se reset ho sakta hai kyunke free disk permanent nahi hota. Agar aap chahte hain data hamesha save rahe, Render ka "Persistent Disk" ($ paid) add karein, ya mujhe bata dein main isay free Postgres database (Render/Supabase free tier) par shift kar dun jo restart se nahi udta.

---

## Step 3: QR code banana

Apna live URL milne ke baad (jaise `https://office-attendance-xxxx.onrender.com`):

```bash
pip install qrcode pillow
python generate_qr.py https://office-attendance-xxxx.onrender.com/checkin
```

Yeh `qr_checkin.png` banayega — isko print karke office ki deewar (entrance) par laga dein.

---

## Roz ka istemal

1. Employee deewar par laga QR scan karta hai
2. Naam chunta hai, PIN dalta hai
3. Phone location ki permission maangega — "Allow" karna zaroori hai
4. Check In dabata hai → time, location, aur Late/Present status save ho jata hai
5. Shaam ko wapas QR scan karke Check Out dabata hai

Owners (Hunain, Hammad, Fahad) chahein to bilkul check-in na karein — unki marzi hai, list mein sirf tashreef k liye maujood hain.

## Admin Dashboard (sirf owners ke liye)

`/admin` par jayein, password dalein:
- **Aaj:** aaj kaun aaya, kaun late hai, kaun absent hai
- **Monthly Report:** kisi bhi mahine ka pura record + CSV download (Excel mein khul jata hai)
- **Employees / PIN:** naya employee add karein, kisi ka PIN badlein, kisi ko inactive karein (jese koi job chor de)

---

## Sawalat ya changes chahiye?

Agar kuch aur chahiye — jaise WhatsApp par roz ki report bhejna, salary/leave calculation, ya multiple branches — mujhe bata dein, main add kar dunga.
