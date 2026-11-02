"""
edge_tracker.py — does the ES scalp bot actually have an edge?

Parses every es_bot_*.log in a folder, dedupes trades, and reports expectancy
per trade (points per contract) with a 95% confidence interval, after costs.

Usage:
    python edge_tracker.py                      # logs in current folder
    python edge_tracker.py C:\\path\\to\\logs
    python edge_tracker.py --since 2026-11-03   # only trades on current code
    python edge_tracker.py --cost 0.25          # round-trip cost in pts (1 MES ~ $1.25 = 0.25)

Verdict logic:
    CI low  > 0 after costs  -> EDGE CONFIRMED
    CI high < 0 after costs  -> NO EDGE
    otherwise                -> UNDECIDED (shows roughly how many more trades)
"""
import re, glob, os, sys, argparse, statistics as st
from collections import defaultdict

BAR = re.compile(r'^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] O:([\d.]+) H:([\d.]+) L:([\d.]+) C:([\d.]+)')
SUB = re.compile(r'Limit (BUY|SELL) (\d+) @ [\d.]+ submitted \(ID: (\d+)\)')
RSN = re.compile(r'Reason: (.+)')
FIL = re.compile(r'FILL CONFIRMED: (LONG|SHORT) @ ([\d.]+) \(order (\d+)\)')
FPX = re.compile(r'Fill: (?:SLD|BOT) ([\d.]+) @ ([\d.]+)')
EXT = re.compile(r'EXIT (LONG|SHORT) @ ([\d.]+) \| (.+)')
PNL = re.compile(r'P&L: ([+\-][\d.]+) pts')
TRD = re.compile(r'Trend: (\w+)(?: \(raw: (\w+)\))?')
RIDE = re.compile(r'RIDE SIGNAL (LONG|SHORT) @ ([\d.]+) \| ATR ([\d.]+)')
ATRL = re.compile(r'ATR: ([\d.]+)')
SHD = re.compile(r'SHADOW WOULD BLOCK (?:LONG|SHORT): (.+)')


RIDE_DAYS = {}   # date -> {'bars': [...], 'signals': [...]}, filled by parse()


def parse(folder):
    trades = {}
    for path in sorted(glob.glob(os.path.join(folder, 'es_bot_*.log'))):
        txt = open(path, encoding='utf-8', errors='replace').read().replace('\r', '')
        if 'SCALP' not in txt and 'clientId=10' not in txt:
            continue
        date = bar = None; prev_bars = []; reasons = {}; last_id = None
        open_t = None; exit_fills = []; pending = None
        shadow = None; shadows = {}
        trend_lbl = ''; labels = {}   # trend label on the bar an order was sent   # shadow tags seen this bar -> attached to the next order
        for ln in txt.split('\n'):
            m = BAR.match(ln)
            if m:
                date = m.group(1)
                bar = dict(t=m.group(2), h=float(m.group(4)), l=float(m.group(5)), c=float(m.group(6)))
                rd = RIDE_DAYS.setdefault(date, {'bars': {}, 'signals': {}})
                rd['bars'][bar['t']] = bar
                prev_bars = (prev_bars + [bar])[-3:]
                shadow = None; trend_lbl = ''
                if pending:   # exit fills land mid-bar, so include the bar that prints next
                    t, fills, lo, hi = pending
                    lo = min(lo, bar['l']); hi = max(hi, bar['h'])
                    t['suspect'] = any(p < lo - 0.01 or p > hi + 0.01 for p in fills)
                    pending = None
                continue
            if bar is None:
                continue
            m = ATRL.search(ln)
            if m and 'RSI:' in ln: bar['atr'] = float(m.group(1))
            m = RIDE.search(ln)
            if m:
                RIDE_DAYS[date]['signals'][bar['t']] = (m.group(1), float(m.group(2)), float(m.group(3)))
            m = TRD.search(ln)
            if m and 'Trend:' in ln and 'blocks' not in ln:
                # confirmed trend, or the raw trend when confirmed is 'sideways'
                trend_lbl = m.group(2) if (m.group(1) == 'sideways' and m.group(2)) else m.group(1)
            m = SHD.search(ln)
            if m: shadow = [x.split()[0] for x in m.group(1).split(' | ')]
            m = SUB.search(ln)
            if m:
                last_id = m.group(3)
                shadows[last_id] = shadow or []
                labels[last_id] = trend_lbl
            m = RSN.search(ln)
            if m and last_id and last_id not in reasons:
                reasons[last_id] = m.group(1).strip()
            m = FIL.search(ln)
            if m:
                r = reasons.get(m.group(3), '')
                lbl = labels.get(m.group(3), '')
                d = 'bull' if 'bullish' in lbl else 'bear' if 'bearish' in lbl else None
                want = 'bull' if m.group(1) == 'LONG' else 'bear'
                if 'sideways' not in r:
                    style = 'trend mode'
                elif d is None:
                    style = 'ranging, no trend'
                else:
                    style = 'ranging, with trend' if d == want else 'FADE (ranging)'
                open_t = dict(style=style, date=date, time=bar['t'], side=m.group(1), entry=float(m.group(2)),
                              mode='ranging' if 'sideways' in r else 'trend',
                              shadow=shadows.get(m.group(3), []))
                exit_fills = []
                continue
            m = FPX.search(ln)
            if m and open_t:
                exit_fills.append(float(m.group(2)))
            m = EXT.search(ln)
            if m and open_t:
                open_t['exit_reason'] = m.group(3).strip()
                # fake-fill check: any exit fill price outside the last few bars' range
                lo = min(b['l'] for b in prev_bars); hi = max(b['h'] for b in prev_bars)
                pending = (open_t, list(exit_fills), lo, hi)
            m = PNL.search(ln)
            if m and open_t and 'exit_reason' in open_t:
                open_t['pts'] = float(m.group(1))
                trades.setdefault((open_t['date'], open_t['time'], open_t['side'], open_t['entry']), open_t)
                open_t = None
    return sorted(trades.values(), key=lambda t: (t['date'], t['time']))


def simulate_rides(since=None, max_per_day=3, trail_k=3.0):
    """Replay logged RIDE SIGNAL lines as if traded: entry at the signal bar close,
    stop max(2xATR, 8) that trails 3xATR behind the best price, no target,
    flat by 14:55 CT, one ride at a time, max 3 per day. Same rules as the
    Aug-Nov backtest. Bar-level, so treat it as an estimate."""
    out = []
    for d in sorted(RIDE_DAYS):
        if since and d < since: continue
        bars = [RIDE_DAYS[d]['bars'][k] for k in sorted(RIDE_DAYS[d]['bars'])]
        sigs = RIDE_DAYS[d]['signals']
        idx = {b['t']: i for i, b in enumerate(bars)}
        busy = -1; n = 0
        for t in sorted(sigs):
            i = idx.get(t)
            if i is None or i <= busy or n >= max_per_day: continue
            side, entry, atr = sigs[t]; L = side == 'LONG'; sg = 1 if L else -1
            stop = entry - sg * max(2 * atr, 8); best = entry; pts = None; j = i
            for j in range(i + 1, len(bars)):
                b = bars[j]
                ts = best - sg * trail_k * atr
                stop = max(stop, ts) if L else min(stop, ts)
                if (L and b['l'] <= stop) or (not L and b['h'] >= stop):
                    pts = sg * (stop - entry); break
                best = max(best, b['h']) if L else min(best, b['l'])
                if b['t'] >= '14:55':
                    pts = sg * (b['c'] - entry); break
            if pts is None:
                pts = sg * (bars[-1]['c'] - entry)
            out.append(dict(date=d, time=t, side=side, pts=round(pts / 0.25) * 0.25))
            busy = j + 2; n += 1
    return out


def stats(v, cost):
    n = len(v)
    if n < 1:
        return None
    net = [x - cost for x in v]
    mean = st.mean(net); sd = st.stdev(net) if n > 1 else 0.0; se = sd / n ** 0.5
    wins = [x for x in v if x > 0]; losses = [x for x in v if x <= 0]
    aw = st.mean(wins) if wins else 0.0; al = st.mean(losses) if losses else 0.0
    be = abs(al) / (aw + abs(al)) if wins and losses else None
    return dict(n=n, win=len(wins) / n, aw=aw, al=al, be=be, mean=mean, sd=sd,
                lo=mean - 1.96 * se, hi=mean + 1.96 * se, total=sum(net))


def line(label, s):
    if not s:
        return f'  {label:20} n/a'
    be = f"{s['be']*100:4.0f}%" if s['be'] is not None else '  - '
    return (f"  {label:20} n={s['n']:4}  win {s['win']*100:4.0f}% (b/e {be})  "
            f"avgW {s['aw']:+5.2f}  avgL {s['al']:+6.2f}  exp {s['mean']:+5.2f}  "
            f"95% CI [{s['lo']:+5.2f}, {s['hi']:+5.2f}]  total {s['total']:+8.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', nargs='?', default='.')
    ap.add_argument('--since', default=None, help='YYYY-MM-DD, count trades on/after this date only')
    ap.add_argument('--cost', type=float, default=0.25, help='round-trip cost in pts per contract')
    a = ap.parse_args()

    T = parse(a.folder)
    if a.since:
        T = [t for t in T if t['date'] >= a.since]
    if len(T) < 2:
        print('Not enough trades.'); return

    pts = [t['pts'] for t in T]
    s = stats(pts, a.cost)
    print(f"\nEDGE REPORT  {T[0]['date']} -> {T[-1]['date']}  |  cost {a.cost} pts/trade  |  "
          f"{len({t['date'] for t in T})} trading days\n")
    print(line('ALL', s))
    print('  -- with trend vs fade --')
    for style in ('trend mode', 'FADE (ranging)', 'ranging, with trend', 'ranging, no trend'):
        v = [t['pts'] for t in T if t['style'] == style]
        if v: print(line(style, stats(v, a.cost)))
    print('  -- by side --')
    for side in ('LONG', 'SHORT'):
        print(line(side.lower(), stats([t['pts'] for t in T if t['side'] == side], a.cost)))
    if len(pts) >= 30:
        print(line('last 30', stats(pts[-30:], a.cost)))

    print('\n  By month:')
    bym = defaultdict(list)
    for t in T: bym[t['date'][:7]].append(t['pts'])
    for m in sorted(bym):
        print(line('  ' + m, stats(bym[m], a.cost)))

    if any(t['shadow'] for t in T):
        print('\n  Shadow filters (trades the filter WOULD have blocked vs the rest, ranging only):')
        R = [t for t in T if t['mode'] == 'ranging']
        for tag in ('persistent', 'rangeextreme'):
            hit = [t['pts'] for t in R if tag in t['shadow']]
            rest = [t['pts'] for t in R if tag not in t['shadow']]
            print(line(f'  {tag}', stats(hit, a.cost)))
            print(line('    the rest', stats(rest, a.cost)))
            print(f"      -> filter would have changed total by {-sum(x - a.cost for x in hit):+.2f} pts")

    rides = simulate_rides(a.since)
    if rides:
        print('\n  Shadow trend RIDE (simulated from logged signals, NOT real trades):')
        print(line('  rides', stats([r['pts'] for r in rides], a.cost)))
        for r in rides[-8:]:
            print(f"      {r['date']} {r['time']} {r['side']:5} {r['pts']:+6.2f}")

    sus = [t for t in T if t.get('suspect')]
    if sus:
        print(f"\n  ⚠ {len(sus)} exit(s) filled outside the bar range (paper fake fills?) — check by hand:")
        for t in sus:
            print(f"     {t['date']} {t['time']} {t['side']} {t['entry']:.2f} -> {t['pts']:+.2f} pts")

    print('\n  VERDICT: ', end='')
    if s['lo'] > 0:
        print(f"EDGE CONFIRMED (95% CI low {s['lo']:+.2f} pts/trade after costs)")
    elif s['hi'] < 0:
        print(f"NO EDGE (95% CI high {s['hi']:+.2f} pts/trade after costs)")
    else:
        msg = f"UNDECIDED — CI spans zero."
        if s['mean'] > 0:
            need = int((1.96 * s['sd'] / s['mean']) ** 2) - s['n']
            msg += f" If the current {s['mean']:+.2f}/trade holds, ~{max(need, 0)} more trades to confirm."
        else:
            msg += " Running negative after costs."
        print(msg)
    print()


if __name__ == '__main__':
    main()