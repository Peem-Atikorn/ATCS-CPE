# Branch และหลักฐานงานของ Peem-Atikorn

บันทึกวันที่ 8 ตุลาคม 2026 จากโปรเจกต์ [Team D-II](https://github.com/sakda1306/Advanced-Topic-in-Computer-Software-Course-Team-D-II)

| Branch ในรีโปนี้ | ต้นทาง | Commit ณ วันที่บันทึก |
|---|---|---|
| [codex/panball-08-deploy-peem-atikorn](https://github.com/Peem-Atikorn/ATCS-CPE/tree/codex/panball-08-deploy-peem-atikorn) | `origin/feature/08-deploy-peem-atikorn` | `12b5139` |
| [codex/panball-08-deploy-completion](https://github.com/Peem-Atikorn/ATCS-CPE/tree/codex/panball-08-deploy-completion) | `peem/08-deploy-completion` ในเครื่อง | `18208d5` |

ทั้งสอง branch เก็บประวัติเดิมและชื่อผู้เขียนเดิมไว้ ข้อมูลใน branch รวมโค้ดของเพื่อนในทีมด้วย
งานหลักที่รับผิดชอบคือโมดูล 08 Deploy & Monitoring ส่วนรายการด้านล่างแสดง commit ที่ระบุ author เป็น Atikorn
บางรายการเป็น commit ที่ cherry-pick จึงมี SHA ต่างกันแต่เนื้อหาซ้ำ ไม่ควรนับเป็นงานใหม่สองครั้ง

## งาน Deploy & Monitoring

- `a9d924a` — เชื่อมบริการจริงด้วย Docker Compose และเพิ่ม CI สำหรับแต่ละโมดูล
- `8fa7a39` — ให้ CI ตรวจเฉพาะโมดูลที่มีการแก้ไข
- `ba852ed` — ปรับคำอธิบาย trigger ของ warmup
- `283d6a3` — เพิ่ม preflight, monitoring, smoke test และรายงาน evaluation
- `97cf7aa` — รองรับ Docker Desktop ที่ติดตั้งในโฟลเดอร์ผู้ใช้ และบันทึกการตรวจระบบจริง

หัว branch `12b5139` เป็น commit ของ sakda1306 ที่แก้การส่ง PLAYER_INDEX_ENABLED ไม่ได้อ้างว่าเป็นงานของ Atikorn

## Commit ที่เขียนโดย Atikorn ใน snapshot

| Commit | วันที่ | รายการ |
|---|---|---|
| [e52357e](https://github.com/Peem-Atikorn/ATCS-CPE/commit/e52357e4b0f00dc4528bce46eef12adc93cadab7) | 2026-10-03 | feat(auth): add local account registration |
| [cbb8ca6](https://github.com/Peem-Atikorn/ATCS-CPE/commit/cbb8ca6cc0ded4b540699c397dca1071bb449a3e) | 2026-10-02 | fix(01-web): keep guest session checks on login page |
| [39c3552](https://github.com/Peem-Atikorn/ATCS-CPE/commit/39c3552392ebce08f0f6149647152688a8964005) | 2026-10-02 | Revert "feat(01-web): add Google registration and sign-in UI" |
| [6c743bc](https://github.com/Peem-Atikorn/ATCS-CPE/commit/6c743bced2693a5927c22cbc1589b49962535e08) | 2026-09-30 | style(generation): apply CI formatting |
| [243282f](https://github.com/Peem-Atikorn/ATCS-CPE/commit/243282f5d950159541e6eac6e96bd35c7443544e) | 2026-09-30 | fix(router): bound historical scorer answers to league seasons |
| [4f89ddb](https://github.com/Peem-Atikorn/ATCS-CPE/commit/4f89ddb193514c7014442dcfba8df40dfdf9a35a) | 2026-09-30 | style(generation): apply CI formatting |
| [abe7bbc](https://github.com/Peem-Atikorn/ATCS-CPE/commit/abe7bbc884b9dfe545da3cffb14bdcc37526b0a4) | 2026-09-30 | fix(router): bound historical scorer answers to league seasons |
| [187e7dc](https://github.com/Peem-Atikorn/ATCS-CPE/commit/187e7dc40c759a0dd1842e42022f6ea22b35dc1f) | 2026-09-30 | fix(football-data): validate scorer ties and reference values |
| [583e897](https://github.com/Peem-Atikorn/ATCS-CPE/commit/583e89731de0b1c009228323ad6e13846e54c6bf) | 2026-09-30 | fix(router): restrict historical scorer shortcut to league queries |
| [6a49029](https://github.com/Peem-Atikorn/ATCS-CPE/commit/6a4902948c6da2919d83f2edda3e5c634b0d0226) | 2026-09-30 | fix(generation): scope scorer ranking guard |
| [1e8b3d0](https://github.com/Peem-Atikorn/ATCS-CPE/commit/1e8b3d01993db2eb5e2d36f4efba11c7993be6c4) | 2026-09-30 | fix(router): handle scorer wording and season context |
| [4bfdeb6](https://github.com/Peem-Atikorn/ATCS-CPE/commit/4bfdeb67d7a2ef82516a2521aeeecfa22d525155) | 2026-09-30 | feat(router): answer verified historical scorer seasons |
| [90571a5](https://github.com/Peem-Atikorn/ATCS-CPE/commit/90571a5ece52a6dce30debd994bb1ae691cd0f04) | 2026-09-30 | feat(football-data): expose verified season top scorers |
| [4f82bed](https://github.com/Peem-Atikorn/ATCS-CPE/commit/4f82bedfaa2d46d03b1462cda66560c09e574a0a) | 2026-09-30 | fix(generation): reject top-scorer claims from player samples |
| [f8c5210](https://github.com/Peem-Atikorn/ATCS-CPE/commit/f8c5210158ca940dcee7e910ebbc24190f92ce3a) | 2026-09-30 | fix(router): route current top-scorer rankings to standings |
| [113d4f7](https://github.com/Peem-Atikorn/ATCS-CPE/commit/113d4f73625f1c4b352c4727deef30f71415ba62) | 2026-09-30 | fix(football-data): validate scorer ties and reference values |
| [3ceb1de](https://github.com/Peem-Atikorn/ATCS-CPE/commit/3ceb1def1ae0befe7aa108c76b8d1cb0eaf96a50) | 2026-09-30 | fix(router): restrict historical scorer shortcut to league queries |
| [9d9b556](https://github.com/Peem-Atikorn/ATCS-CPE/commit/9d9b556780a13d948ba81de32ecc46d1284d2183) | 2026-09-30 | fix(generation): scope scorer ranking guard |
| [5fe3626](https://github.com/Peem-Atikorn/ATCS-CPE/commit/5fe362646de99aea317f734d8b3dca3717b10e6a) | 2026-09-30 | fix(router): handle scorer wording and season context |
| [17d0e6c](https://github.com/Peem-Atikorn/ATCS-CPE/commit/17d0e6c54687935d4b1a5d42e41e302ab9267173) | 2026-09-30 | feat(router): answer verified historical scorer seasons |
| [69c1f6e](https://github.com/Peem-Atikorn/ATCS-CPE/commit/69c1f6ea2277a8ff6322f7d98bed69dba33e8c45) | 2026-09-30 | feat(football-data): expose verified season top scorers |
| [0029229](https://github.com/Peem-Atikorn/ATCS-CPE/commit/0029229aaf9bcc38cc7a867c7b6acd8318497482) | 2026-09-30 | fix(generation): reject top-scorer claims from player samples |
| [7c3342b](https://github.com/Peem-Atikorn/ATCS-CPE/commit/7c3342b091302427f12ff173f8744c9b2ea9be14) | 2026-09-30 | fix(router): route current top-scorer rankings to standings |
| [97cf7aa](https://github.com/Peem-Atikorn/ATCS-CPE/commit/97cf7aa4715265a12fa79eec2f72d399b9ad1b73) | 2026-09-30 | fix(deploy): detect user Docker Desktop and record live verification |
| [283d6a3](https://github.com/Peem-Atikorn/ATCS-CPE/commit/283d6a3f26178a1bc9ae55a78c41afa25ed85e75) | 2026-09-30 | feat(deploy): add stack preflight monitoring smoke and eval |
| [ba852ed](https://github.com/Peem-Atikorn/ATCS-CPE/commit/ba852ed68c42979ff4bf6bdacecf39c5f708fa9f) | 2026-09-26 | docs(deploy): clarify warmup ingest trigger label |
| [8fa7a39](https://github.com/Peem-Atikorn/ATCS-CPE/commit/8fa7a395b99d94036f2ed02aa9c6991386e246c8) | 2026-09-26 | fix(ci): run module checks only when module code changes |
| [a9d924a](https://github.com/Peem-Atikorn/ATCS-CPE/commit/a9d924acb710b467b12b6d51e24b195f46bb8aa3) | 2026-09-26 | feat(deploy): add real-service compose and module CI gates |

รายละเอียดไฟล์ของแต่ละ commit อยู่ใน [contribution.json](contribution.json)
โค้ดที่นำส่งอยู่ใน [PANBALL](PANBALL/) ที่ commit `18208d5875d494f2f8e4f8978038ebad78ffe9c8`
