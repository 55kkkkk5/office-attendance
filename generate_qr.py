"""
Generates a printable QR code that points to your check-in page.

Usage:
    python generate_qr.py https://your-app-url.onrender.com/checkin

This creates qr_checkin.png - print it and stick it on the office wall.
"""
import sys
import qrcode

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_qr.py <checkin-url>")
        print("Example: python generate_qr.py https://myoffice.onrender.com/checkin")
        sys.exit(1)

    url = sys.argv[1]
    img = qrcode.make(url, box_size=12, border=4)
    img.save("qr_checkin.png")
    print(f"Saved qr_checkin.png for URL: {url}")
    print("Print this and stick it on the wall near the entrance.")

if __name__ == "__main__":
    main()
