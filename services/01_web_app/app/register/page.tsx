"use client";

import Link from "next/link";
import { ArrowRight, Bookmark, MessageCircle, Trophy } from "lucide-react";
import { AuthStory } from "../../components/AuthStory";
import { GoogleSignIn } from "../../components/GoogleSignIn";
import { useApp } from "../../components/AppProvider";

export default function Register() {
  const app = useApp();
  return (
    <main className="login-page register-page" id="content">
      <AuthStory />
      <section className="login-form-area">
        <div className="login-form">
          <span className="eyebrow">JOIN THE PANBALL COMMUNITY</span>
          <h2>เข้าร่วม PANBALL</h2>
          <p className="muted">พื้นที่ฟุตบอลของคุณ เริ่มได้ด้วยบัญชี Google</p>
          <div className="register-benefits" aria-label="สิ่งที่สมาชิกทำได้">
            <p>
              <MessageCircle aria-hidden="true" size={20} />{" "}
              ถามเรื่องฟุตบอลพร้อมดูแหล่งข้อมูล
            </p>
            <p>
              <Trophy aria-hidden="true" size={20} />{" "}
              ติดตามข้อมูลทีมและการแข่งขัน
            </p>
            <p>
              <Bookmark aria-hidden="true" size={20} /> บันทึกแมตช์ที่สนใจ
            </p>
          </div>
          {app.user ? (
            <>
              <p>เข้าสู่ระบบแล้ว: {app.user.display_name}</p>
              <Link href="/" className="button primary">
                กลับหน้าเว็บ <ArrowRight size={18} />
              </Link>
            </>
          ) : (
            <>
              <GoogleSignIn />
              <p className="auth-privacy">
                ระบบจะใช้ชื่อและอีเมลจากบัญชี Google เพื่อสร้างบัญชี PANBALL
                ครั้งแรกที่เข้าร่วม ทีมโปรดเลือกได้ภายหลังในตั้งค่าส่วนตัว
              </p>
              <p className="auth-switch">
                มีบัญชีแล้ว? <Link href="/login">เข้าสู่ระบบ</Link>
              </p>
            </>
          )}
          <div
            className="login-pet"
            role="img"
            aria-label={"มาสคอส " + app.team.name}
            style={{ backgroundImage: "url(" + app.team.mascot + ")" }}
          />
        </div>
      </section>
    </main>
  );
}
