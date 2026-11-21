// 自動運転ボット（verify_vm.mjs と tap_check.mjs で使う）。
// 人間の運転士のように、制限速度と停止位置に向けてノッチを選ぶ。
//   h: {num(名前), get(名前)} … ゲームの変数・リストを読む関数
//   desiredNotch(h, state) → 目標のノッチ（5〜1 力行、0 N、−1〜−8 ブレーキ）
export function makeBot({style = 'expert', seed = 7, reckless = false} = {}) {
    // 運転のくせ（停止位置の狙いのずれ・止まる直前にブレーキを緩めるか・制限への余裕・ノッチ操作の間隔）
    const STYLE = {
        expert: {aim: [0, 0], ease: 0.9, margin: -1.5, plan: 3.4, every: 1},
        careful: {aim: [-1.4, 1.0], ease: 1.3, margin: -8, plan: 3.0, every: 3},
        sloppy: {aim: [-3.5, 3.0], ease: 2.2, margin: 4, plan: 4.2, every: 5},
    }[style];
    const rand = () => {
        seed |= 0;
        seed = seed + 0x6D2B79F5 | 0;
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };

    function desiredNotch(h, state) {
        const v = h.num('速度');
        const pos = h.num('位置');
        const lim = h.num('現在の制限');
        const idx = h.num('次の駅番号');
        const stop = Number(h.get('駅の位置')[idx - 1]);
        if (state.station !== idx) {
            state.station = idx;
            state.creep = false;
            state.offset = STYLE.aim[0] + (STYLE.aim[1] - STYLE.aim[0]) * rand();
        }
        const dReal = stop - pos;
        const d = dReal + state.offset;
        state.dReal = dReal;
        state.tolerance = h.num('停止位置の許容');
        const per = h.num('常用最大減速度') / 8;
        const cell = Math.floor(pos / 10);
        const grade = Number(h.get('勾配表')[cell] || 0) * 0.0353;
        const plan = STYLE.plan;
        if (reckless) {
            const reckStop = Math.sqrt(Math.max(0, 2 * 2.5 * 3.6 * (d - v / 3.6 * 1.2)));
            if (reckStop < v + 2 || d < 40) return brakeToStop(h, v, d, per, grade, state);
            return v < h.num('路線の最高速度') + 15 ? 5 : 0;
        }
        let target = lim + STYLE.margin;
        const starts = h.get('制限の開始'), speeds = h.get('制限の速度');
        for (let i = 0; i < starts.length; i++) {
            const s = Number(starts[i]);
            if (s > pos) {
                const vl = Number(speeds[i]) + STYLE.margin;
                const allow = Math.sqrt(Math.max(0, vl * vl + 2 * plan * 3.6 * (s - pos - v / 3.6 * 1.5)));
                target = Math.min(target, allow);
            }
        }
        const stopCurve = Math.sqrt(Math.max(0, 2 * plan * 3.6 * (d - v / 3.6 * 1.2)));
        if (stopCurve < v + 2 || d < 40) return brakeToStop(h, v, d, per, grade, state);
        target = Math.min(target, stopCurve);
        const err = target - v;
        if (err > 0) return Math.min(5, Math.max(1, Math.round(err * 0.6 + grade * 2)));
        if (err > -1.5) return 0;
        return -Math.min(6, Math.max(1, Math.round(-err * 0.6 - grade)));
    }

    function brakeToStop(h, v, d, per, grade, state) {
        if (v < 0.05) {
            if (state.dReal > state.tolerance - 0.3) {
                state.offset = 0;   // 手前すぎて採点されなかったので、停止位置まで進め直す
                d = state.dReal;
            }
            if (d > 0.9) {
                state.creep = true;
                return grade > 0.3 ? 5 : 2;   // 上り坂では強めに力行しないと動かない
            }
            return -8;
        }
        if (state.creep && v < 30) {
            if (v < 4 && d > 3) return grade > 0.3 ? 5 : 2;
            if (d > 30) return v < 30 ? 4 : 0;
            if (d > 0.6 && v < 2.5) return 0;
            state.creep = false;
        }
        const dd = Math.max(0.02, d - v / 3.6 * 0.45);
        const req = v * v / (2 * 3.6 * dd);
        const gain = v < 15 ? 1 + 0.25 * (1 - v / 15) : 1;
        const res = 0.05 + grade;
        let n = (req - res) / (per * gain);
        if (v < 10) n *= STYLE.ease;
        if (n < 0.35) return d > 1 && v < 6 ? 0 : -1;
        return -Math.min(8, Math.max(1, Math.round(n)));
    }

    return {STYLE, desiredNotch, rand};
}
