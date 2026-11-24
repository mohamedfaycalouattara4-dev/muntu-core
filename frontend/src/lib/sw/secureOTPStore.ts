/**
 * SecureOTPStore — AES-GCM encrypted IndexedDB pour OTP de livraison.
 * Conformité V2 §13.2 : OTP jamais en clair côté client.
 */
import CryptoJS from "crypto-js";

const SALT_KEY = "kalyce-otp-salt";

function deviceFingerprintKey(): string {
  const seed = [
    navigator.userAgent,
    navigator.language,
    screen.width + "x" + screen.height,
    new Date().getTimezoneOffset()
  ].join("|");
  return CryptoJS.PBKDF2(seed, SALT_KEY, { keySize: 256 / 32, iterations: 1000 }).toString();
}

export async function storeOtpInApp(orderId: string, otpCode: string) {
  localStorage.setItem(
    `kalyce-otp:${orderId}`,
    CryptoJS.AES.encrypt(otpCode, deviceFingerprintKey()).toString()
  );
}

export function readOtpInApp(orderId: string): string | null {
  const cipher = localStorage.getItem(`kalyce-otp:${orderId}`);
  if (!cipher) return null;
  try {
    const bytes = CryptoJS.AES.decrypt(cipher, deviceFingerprintKey());
    return bytes.toString(CryptoJS.enc.Utf8);
  } catch {
    return null;
  }
}

export function clearOtp(orderId: string) {
  localStorage.removeItem(`kalyce-otp:${orderId}`);
}
