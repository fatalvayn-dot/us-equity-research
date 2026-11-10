"""Select valuation evidence from the latest safe SEC checkpoint."""
import os

from scripts.live_checkpoint import find_checkpoint, require_first_attempt


def select_source(requested='', *, fetch=None):
    if requested and (not requested.isascii() or not requested.isdecimal()
                      or requested.startswith('0')):
        raise ValueError('Kaynak run ID pozitif sayı olmalıdır')
    run, artifacts = find_checkpoint(None, requested, fetch=fetch)
    run_id = run['id']
    if run.get('conclusion') != 'success':
        raise ValueError(f'Son SEC durumunun üretim koşusu başarılı değil ({run_id})')
    evidence = [item for item in artifacts if item['name'] == 'live-acceptance-evidence']
    if len(evidence) != 1 or evidence[0].get('expired') is not False:
        raise ValueError(f'Son SEC durumunun kanıt paketi eksik veya kullanılamıyor ({run_id})')
    return run_id


if __name__ == '__main__':
    require_first_attempt()
    print(select_source(os.environ.get('SOURCE_RUN_INPUT', '')))
