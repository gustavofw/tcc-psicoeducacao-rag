"""Registra o uso de memória do processo no log (somente Linux/Render)."""


def log_memoria(rotulo):
    try:
        info = {}
        with open("/proc/self/status") as f:
            for linha in f:
                if linha.startswith(("VmRSS", "RssAnon", "RssFile", "VmHWM")):
                    chave, valor = linha.split(":")
                    info[chave] = int(valor.split()[0]) // 1024  # kB -> MB
        cgroup = None  # o que a Render de fato contabiliza
        for caminho in ("/sys/fs/cgroup/memory.current",
                        "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
            try:
                with open(caminho) as f:
                    cgroup = int(f.read()) // (1024 * 1024)
                break
            except OSError:
                continue
        print(
            f"[MEM] {rotulo}: rss={info.get('VmRSS')}MB "
            f"(anon={info.get('RssAnon')} arquivo={info.get('RssFile')}) "
            f"pico={info.get('VmHWM')}MB cgroup={cgroup}MB",
            flush=True,
        )
    except Exception:
        pass  # no Windows não existe /proc; simplesmente ignora