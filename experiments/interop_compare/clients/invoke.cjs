// Trusted bridge only. The common Python boundary validates snapshots and decisions.
// No provider SDK, network adapter, authority, or runtime policy lives here.
"use strict";
const fs = require("node:fs");
const policy = require(process.argv[2]);
const value = policy.next(JSON.parse(fs.readFileSync(0, "utf8")));
process.stdout.write(JSON.stringify(value));
