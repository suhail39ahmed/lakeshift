# Judge demo Oracle on Google Cloud

The hosted Streamlit app needs an Oracle it can reach to run the full live migration. This is a
throwaway database on a Google Cloud VM that holds **only synthetic sample data**. Real customer
data never goes here; in production LakeShift brings the code to the data (see README).

Each live run recreates its tables and loads the sample CSVs itself, so no seed script is needed.

## 1. Project and billing (PowerShell, on your laptop)

```powershell
$P = "lakeshift-demo-$(Get-Random -Minimum 10000 -Maximum 99999)"
gcloud projects create $P --name="LakeShift Demo"
gcloud billing projects link $P --billing-account=<BILLING_ACCOUNT_ID>
gcloud config set project $P
gcloud services enable compute.googleapis.com
```

## 2. VM and firewall

```powershell
gcloud compute instances create lakeshift-oracle --zone=asia-south1-a --machine-type=e2-medium --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud --boot-disk-size=30GB --tags=oracle-demo
gcloud compute firewall-rules create allow-oracle-demo --allow=tcp:1521 --target-tags=oracle-demo --source-ranges=0.0.0.0/0
```

Port 1521 is open to all addresses because Streamlit Community Cloud has no fixed outbound IP.
The protections are: synthetic data only, a non-admin demo user, a strong password, the judge
access code and the daily run cap.

## 3. Docker and Oracle (on the VM)

```powershell
gcloud compute ssh lakeshift-oracle --zone=asia-south1-a
```

```bash
sudo apt-get update && sudo apt-get install -y docker.io
read -s -p "New Oracle SYSTEM password: " OPW; echo
sudo docker run -d --name oracle --restart unless-stopped -p 1521:1521 -e ORACLE_PASSWORD="$OPW" gvenzl/oracle-free:23-slim
sudo docker logs -f oracle   # wait for "DATABASE IS READY TO USE!", then Ctrl+C
```

## 4. Demo user

```bash
sudo docker exec -it oracle sqlplus / as sysdba
```

```sql
ALTER SESSION SET CONTAINER = FREEPDB1;
CREATE USER lakeshift_demo IDENTIFIED BY "<demo password>" QUOTA 500M ON USERS;
GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE SEQUENCE, CREATE TYPE, CREATE SYNONYM TO lakeshift_demo;
EXIT
```

Use letters and numbers only for the password. Then `exit` the VM.

## 5. Test from your laptop

```powershell
$IP = gcloud compute instances describe lakeshift-oracle --zone=asia-south1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
Test-NetConnection $IP -Port 1521   # expect TcpTestSucceeded : True
```

## 6. Streamlit secrets

In the hosted app, **Settings > Secrets** (never commit these):

```toml
ORACLE_HOST = "<VM public IP>"
ORACLE_PORT = "1521"
ORACLE_USER = "lakeshift_demo"
ORACLE_PASSWORD = "<demo password>"
ORACLE_SERVICE = "FREEPDB1"
JUDGE_ACCESS_CODE = "<pick a code>"
LIVE_RUNS_PER_DAY = "10"
```

## Cost and cleanup

At list prices in Mumbai, running 24/7 costs about **$30-35 a month** (e2-medium VM, 30 GB disk,
public IP). Free trial credit covers it. Stopped, only the disk is billed (about $3 a month);
the public IP may change on restart, so update `ORACLE_HOST`.

```powershell
gcloud compute instances stop lakeshift-oracle --zone=asia-south1-a    # pause
gcloud compute instances start lakeshift-oracle --zone=asia-south1-a   # resume
gcloud compute instances delete lakeshift-oracle --zone=asia-south1-a  # remove the VM
gcloud projects delete $P                                               # remove everything
```
