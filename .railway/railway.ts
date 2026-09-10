import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const Postgres = postgres("Postgres", { region: "us-west2" });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-west2", sizeMB: 5000 });
  const web = service("web", {
    source: github("Educcorp/raspy-face-lockers", { checkSuites: false }),
    replicas: { "us-west2": 1 },
    env: { DATABASE_URL: preserve(), SECRET_KEY: preserve() },
  });

  return project("raspi-lockers", {
    resources: [web, Postgres, postgresVolume],
  });
});
