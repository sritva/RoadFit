import requests
res = requests.get('https://api.github.com/repos/sritva/RoadFit/actions/runs')
data = res.json()
if 'workflow_runs' in data and len(data['workflow_runs']) > 0:
    run = data['workflow_runs'][0]
    print(f"Run ID: {run['id']}, Status: {run['conclusion']}")
    jobs_res = requests.get(run['jobs_url'])
    jobs = jobs_res.json()
    if 'jobs' in jobs and len(jobs['jobs']) > 0:
        job = jobs['jobs'][0]
        print(f"Job ID: {job['id']}, Status: {job['conclusion']}")
        print(f"Log URL: https://api.github.com/repos/sritva/RoadFit/actions/jobs/{job['id']}/logs")
else:
    print('No runs found', data)
