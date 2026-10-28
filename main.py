import json, os, subprocess, sys, tempfile, urllib.request

from playwright.sync_api import sync_playwright


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'render'}), timeout=60) as r:
        return r.read()


def main():
    job = json.loads(get(sys.argv[1]))
    w, h, fps = job['width'], job['height'], job.get('fps', 30)
    tmp = tempfile.mkdtemp()
    silent, final = os.path.join(tmp, 'silent.mp4'), os.path.join(tmp, 'final.mp4')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': w, 'height': h})
        page.goto(job['page'])
        page.wait_for_selector('body[data-pronto], body[data-ready]', timeout=60000)
        duration = page.evaluate(f"window[{json.dumps(job['duration'])}]")
        cues = page.evaluate(f"window[{json.dumps(job['events'])}] || []")
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'mjpeg', '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-maxrate', '4M', '-bufsize', '8M',
                                '-pix_fmt', 'yuv420p', silent], stdin=subprocess.PIPE)
        for i in range(int(duration * fps)):
            page.evaluate(f"window[{json.dumps(job['draw'])}]({i / fps})")
            enc.stdin.write(page.screenshot(type='jpeg', quality=92, clip={'x': 0, 'y': 0, 'width': w, 'height': h}))
        enc.stdin.close()
        if enc.wait() != 0:
            sys.exit('video encoding failed')
        browser.close()
    inputs, filters, n = ['-i', silent], [], 0
    if job.get('music'):
        path = os.path.join(tmp, 'music.mp3')
        open(path, 'wb').write(get(job['music']['url']))
        inputs += ['-i', path]
        filters.append(f"[1:a]atrim=0:{duration},volume={job['music'].get('volume', 0.45)},afade=t=in:d=0.4,afade=t=out:st={max(0, duration - 1.5)}:d=1.5[m]")
        n = 1
    cache = {}
    for i, (t, f, v) in enumerate(cues):
        if f not in cache:
            cache[f] = os.path.join(tmp, f'cue{len(cache)}.mp3')
            open(cache[f], 'wb').write(get(job['sounds'] + f))
        inputs += ['-i', cache[f]]
        ms = int(t * 1000)
        filters.append(f'[{len(inputs) // 2 - 1}:a]volume={v},adelay={ms}|{ms}[c{i}]')
    mix = ('[m]' if n else '') + ''.join(f'[c{i}]' for i in range(len(cues)))
    count = n + len(cues)
    if count:
        filters.append(f'{mix}amix=inputs={count}:normalize=0,volume=1.5,alimiter=limit=0.95[a]')
        cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filters), '-map', '0:v', '-map', '[a]',
               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', str(duration), '-movflags', '+faststart', final]
    else:
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', silent, '-c', 'copy', '-movflags', '+faststart', final]
    if subprocess.run(cmd).returncode != 0:
        sys.exit('audio mix failed')

    if job.get('upload') == 'litterbox':
        up = subprocess.run(['curl', '-s', '-F', 'reqtype=fileupload', '-F', 'time=72h', '-F', f'fileToUpload=@{final}',
                             'https://litterbox.catbox.moe/resources/internals/api.php'], capture_output=True, text=True)
        link = up.stdout.strip()
        if not link.startswith('https://'):
            sys.exit('upload failed')
        data, kind = json.dumps({'url': link}).encode(), 'application/json'
    else:
        data, kind = open(final, 'rb').read(), 'video/mp4'
    req = urllib.request.Request(job['done'], data=data, method='POST', headers={'Content-Type': kind, 'User-Agent': 'render'})
    with urllib.request.urlopen(req, timeout=120) as r:
        print('delivered, status', r.status)


if __name__ == '__main__':
    main()
