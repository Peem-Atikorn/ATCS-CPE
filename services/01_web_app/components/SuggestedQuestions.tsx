"use client";
import { useApp } from "./AppProvider";
import { useRemote } from "../lib/use-remote";
import { Match } from "../lib/types";
import { nextMatch } from "../lib/matchday";
export function SuggestedQuestions() {
  const app = useApp();
  const team = app.browsingTeam;
  const fixtures = useRemote<{ matches: Match[] }>(
    `/football/fixtures?team_id=${team.teamId}`,
  );
  const next = nextMatch(fixtures.data?.matches ?? [], team.teamId);
  const opponent =
    next && (next.home.team_id === team.teamId ? next.away : next.home);
  const general = [
    `สรุปผลการแข่งขันล่าสุดของ ${team.name}`,
    `${team.name} นัดต่อไปเจอใคร`,
    `${team.name} อยู่อันดับเท่าไหร่`,
    `${team.name} มีนักเตะคนไหนบ้าง`,
    `สรุปผลงานสัปดาห์ล่าสุดของ ${team.name}`,
  ];
  const predictions = [
    opponent
      ? `${team.name} กับ ${opponent.name} ใครจะชนะ?`
      : "ใครจะได้แชมป์พรีเมียร์ลีกปีนี้?",
    `${team.name} มีโอกาสติดท็อป 4 กี่เปอร์เซ็นต์?`,
  ];
  return (
    <div className="suggested-questions">
      <p>ลองเริ่มด้วยคำถามเกี่ยวกับ {team.shortName}</p>
      {general.map((prompt) => (
        <button key={prompt} onClick={() => app.ask(prompt)}>
          {prompt}
        </button>
      ))}
      <span className="eyebrow">ทำนายผล</span>
      {predictions.map((prompt) => (
        <button key={prompt} onClick={() => app.ask(prompt)}>
          {prompt}
        </button>
      ))}
      <small>เลือกคำถามเพื่อเติมข้อความ แล้วกดส่ง</small>
    </div>
  );
}
