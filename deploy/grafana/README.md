# Grafana dashboard "App Sport"

`app-sport.json` is the dashboard of the app on the VPS: whether the three
containers of the Coolify project `app-sport` run, how often they restart, and
the memory, processor, network and disk they use.

It only reads what Prometheus **already** collects for the `supervision`
project (cAdvisor for the containers, node-exporter for the disk). Nothing in
`supervision` or in the JobRadar repository has to change.

## Installing it (once)

1. In Grafana: **Dashboards › New › New folder**, name it `App Sport`.
2. **Dashboards › New › Import**, upload `app-sport.json`, choose the folder
   `App Sport` and the existing Prometheus data source, then **Import**.
3. Its address ends in `/d/app-sport`. Put it in the Coolify variable
   `GRAFANA_URL` of the `app-sport` project so that Réglages › Monitoring shows
   an "Ouvrir dans Grafana" button.

The same can be done with Grafana's HTTP API (`POST /api/folders`, then
`POST /api/dashboards/import` with the `DS_PROMETHEUS` input).

## Changing it

Edit the dashboard in Grafana, then **Export › Export as JSON** with
"Export for sharing externally" ticked, and replace `app-sport.json` here, so the
repository keeps the reference copy. The dashboard is not provisioned from
files: if Grafana is ever reinstalled, import it again.

## Containers it looks for

cAdvisor names containers after the Coolify services: `sport-app-…`,
`sport-tailscale-…`, `sport-backup-…`. Renaming a service in
`docker-compose.yml` means updating the `name=~"^sport-…"` filters here.
