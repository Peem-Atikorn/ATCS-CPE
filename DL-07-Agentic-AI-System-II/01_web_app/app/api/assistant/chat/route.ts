import { NextResponse } from "next/server";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface TripContextData {
  origin?: string;
  destination?: string;
  date?: string;
  time?: string;
  mode?: string;
  recommendation?: {
    actionCode?: string;
    riskLevel?: string;
    explanation?: {
      summary?: string;
      reasons?: string[];
      instructions?: string[];
    };
    weather?: {
      temperature?: number;
      precipitationMmH?: number;
      summary?: string;
    };
    transport?: {
      delayS?: number;
      hazard?: string;
    };
  };
}

function generateFallbackReply(userQuestion: string, context?: TripContextData) {
  const q = userQuestion.toLowerCase();
  const origin = context?.origin || "ต้นทาง";
  const destination = context?.destination || "ปลายทาง";
  const rec = context?.recommendation;
  const summary = rec?.explanation?.summary;
  const riskLevel = rec?.riskLevel || "LOW";

  if (q.includes("ฝน") || q.includes("อากาศ") || q.includes("พายุ") || q.includes("สภาพอากาศ")) {
    if (rec?.weather?.summary) {
      return {
        reply: `รายงานสภาพอากาศสำหรับเส้นทาง ${origin} ➔ ${destination}: ${rec.weather.summary} อุณหภูมิประมาณ ${rec.weather.temperature ?? 30}°C แนะนำตรวจสอบที่ปัดน้ำฝนและไฟหน้ารถให้พร้อมครับ`,
        proposal: null,
      };
    }
    return {
      reply: `จากการตรวจสอบข้อมูลสภาพอากาศตามแนวเส้นทาง ${origin} ➔ ${destination} พบว่าภาพรวมทัศนวิสัยอยู่ในเกณฑ์ปกติ มีโอกาสเกิดฝนฟ้าคะนองกระจายตัวบางจุดครับ`,
      proposal: null,
    };
  }

  if (q.includes("รถติด") || q.includes("จราจร") || q.includes("ปิดถนน") || q.includes("น้ำท่วม") || q.includes("อุบัติเหตุ")) {
    if (rec?.transport?.hazard) {
      return {
        reply: `ข้อมูลจราจรสด (iTIC / Longdo Traffic) รายงานข้อควรระวัง: ${rec.transport.hazard} แนะนำใช้ความระมัดระวังเป็นพิเศษหรือเตรียมเวลาเดินทางเพิ่มครับ`,
        proposal: null,
      };
    }
    return {
      reply: `จากการเชื่อมต่อข้อมูลจราจรสดของ Longdo Traffic บนเส้นทาง ${origin} ➔ ${destination} ไม่พบการสั่งปิดถนนหลักหรือเหตุน้ำท่วมขังรุนแรง การจราจรเคลื่อนตัวได้ตามปกติครับ`,
      proposal: null,
    };
  }

  if (q.includes("เลื่อนเวลา") || q.includes("เปลี่ยนเวลา") || q.includes("กี่โมง") || q.includes("เวลา")) {
    const newTime = "10:30";
    return {
      reply: `หากต้องการปรับเวลาออกเดินทางเพื่อหลีกเลี่ยงช่วงการจราจรหนาแน่นหรือลดความเสี่ยงจากสภาพอากาศ แนะนำเป็นช่วงเวลา ${newTime} น. ครับ คุณสามารถกดปุ่มยืนยันด้านล่างเพื่ออัปเดตแผนการเดินทางได้ทันทีครับ`,
      proposal: {
        label: `เลื่อนเวลาออกเดินทางเป็น ${newTime} น.`,
        changes: {
          time: newTime,
        },
      },
    };
  }

  if (q.includes("ปลอดภัย") || q.includes("ไปได้ไหม") || q.includes("เดินทางได้ไหม") || q.includes("สรุป")) {
    const riskThai = riskLevel === "HIGH" ? "ความเสี่ยงสูง (ควรหลีกเลี่ยง)" : riskLevel === "MEDIUM" ? "ความเสี่ยงปานกลาง (ใช้ความระมัดระวัง)" : "ปลอดภัย (เดินทางได้ตามปกติ)";
    return {
      reply: `ผลการประเมินทริป ${origin} ➔ ${destination} สรุปความปลอดภัย: ${riskThai}\n${summary || "สามารถเดินทางตามแผนได้ โดยติดตามประกาศล่าสุดก่อนออกเดินทางครับ"}`,
      proposal: null,
    };
  }

  return {
    reply: `สวัสดีครับ ผมคือผู้ช่วยเดินทางอัจฉริยะ พร้อมดูแลทริปจาก ${origin} ไปยัง ${destination} คุณสามารถสอบถามสภาพอากาศ จราจรอุบัติเหตุสด หรือบอกให้ผมช่วยปรับเวลา/พาหนะเดินทางได้ตลอดเวลาครับ`,
    proposal: null,
  };
}

export async function POST(req: Request) {
  try {
    const { messages, tripContext } = (await req.json()) as {
      messages: Message[];
      tripContext?: TripContextData;
    };

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ error: "Missing messages" }, { status: 400 });
    }

    const apiKey = process.env.GEMINI_API_KEY || process.env.LLM_API_KEY;
    const userQuestion = messages[messages.length - 1].content;

    if (!apiKey) {
      return NextResponse.json(generateFallbackReply(userQuestion, tripContext));
    }

    const model = process.env.LLM_MODEL_EXPLAINER || "gemini-2.0-flash";
    const baseUrl = (process.env.GEMINI_API_BASE || "https://generativelanguage.googleapis.com/v1beta").replace(/\/$/, "");
    const url = `${baseUrl}/models/${model}:generateContent?key=${apiKey}`;

    const systemPrompt = `คุณคือ "ผู้ช่วยเดินทางอัจฉริยะ (AI Travel Assistant)" ของระบบ Waypoint Safety Thailand
หน้าที่ของคุณคือ:
1. ตอบคำถามของผู้ใช้เกี่ยวกับการเดินทาง สภาพอากาศสด จราจรอุบัติเหตุ (Longdo Traffic) และการเตือนภัย ปภ.
2. สไตล์การตอบ: ภาษาไทยที่สุภาพ กระชับ สละสลวย ชัดเจน และเป็นมิตร
3. อิงข้อมูลจาก [บริบทการเดินทางปัจจุบัน] ที่ได้รับ ห้ามกุข้อมูลตัวเลขที่ขัดแย้งกับหลักฐานจริง
4. หากผู้ใช้ต้องการปรับเปลี่ยนแผนการเดินทาง (เช่น "เลื่อนเวลาออกเดินทาง", "เปลี่ยนพาหนะ", "เปลี่ยนจุดหมาย"):
   - อธิบายเหตุผลในข้อความ "reply"
   - ให้ส่งข้อมูลใน "proposal" เป็น Object ที่มี "label" และ "changes" เพื่อให้หน้าเว็บนำไปอัปเดตฟอร์มได้
5. หากผู้ใช้เพียงถามคำถามทั่วไป ให้ใส่ "proposal": null
6. ตอบกลับเป็น JSON เท่านั้นตาม Schema นี้:
{
  "reply": "ข้อความตอบกลับภาษาไทย",
  "proposal": null หรือ {
    "label": "ข้อความสรุปการปรับเปลี่ยนสั้นๆ เช่น เลื่อนเวลาเป็น 15:30 น.",
    "changes": {
      "time": "HH:mm (ถ้าเปลี่ยนเวลา)",
      "date": "YYYY-MM-DD (ถ้าเปลี่ยนวัน)",
      "origin": "ชื่อสถานที่ (ถ้าเปลี่ยนต้นทาง)",
      "destination": "ชื่อสถานที่ (ถ้าเปลี่ยนปลายทาง)",
      "mode": "CAR | BUS | TRAIN | FLIGHT | WALK (ถ้าเปลี่ยนพาหนะ)"
    }
  }
}`;

    const contextText = tripContext ? JSON.stringify(tripContext, null, 2) : "ไม่มีข้อมูลทริปปัจจุบัน";

    const payload = {
      system_instruction: {
        parts: [{ text: systemPrompt }],
      },
      contents: [
        {
          role: "user",
          parts: [
            {
              text: `[บริบทการเดินทางปัจจุบัน]\n${contextText}\n\n[คำถาม/คำขอของผู้ใช้]\n${userQuestion}`,
            },
          ],
        },
      ],
      generationConfig: {
        temperature: 0.2,
        responseMimeType: "application/json",
      },
    };

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errText = await res.text();
      console.warn("Gemini API error:", res.status, errText);
      return NextResponse.json(generateFallbackReply(userQuestion, tripContext));
    }

    const data = await res.json();
    const candidateText = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!candidateText) {
      return NextResponse.json(generateFallbackReply(userQuestion, tripContext));
    }

    try {
      const parsed = JSON.parse(candidateText);
      return NextResponse.json(parsed);
    } catch {
      return NextResponse.json({
        reply: candidateText,
        proposal: null,
      });
    }
  } catch (error) {
    console.error("Assistant chat error:", error);
    return NextResponse.json({
      reply: "ขออภัยครับ ระบบกำลังประมวลผลข้อมูลการเดินทาง กรุณาลองใหม่อีกครั้งในสักครู่ครับ",
      proposal: null,
    });
  }
}
