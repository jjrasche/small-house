# Coldest-week heat view (stage: blueprint)

engine 8199: master 46f9dfa CLI (build-out engine-46f9dfa/20261027T024350-0bba), -Xmx1g, repository property = a copy of 46f9dfa's contract parent, roots = worlds worktree small-house-coldest-week and small-house. Live engines 8198/8197 untouched.

Heat view: no engine change. The live serve-worlds jar (build 25c9bc95-828f1113) was started a second time on 127.0.0.1:8094 with `--engine http://127.0.0.1:8199`; the live 8090 page still points at 8198.

Views are bound to a world by their `world` field, so the existing greenhouse/views/heat.heat.json only appears under greenhouse-seventy. Added in the worlds worktree: views/heat-coldest-week.heat.json and views/seventy-coldest-week.site.json (copies, world and site re-pointed).

Block found: `simulate` on seventy-coldest-week.json (clock until 168) is refused: "thermal.hold-air-hour: the heat network window holds 167 hours, but step 167 needs one". The heat view also needs whole 24-hour days. Workaround for this run: seventy-coldest-week-t167.json (id ...-t167, until 167), which the two views are bound to. Fix belongs in the climate domain window (168 hours) or the world clock.

Page: http://127.0.0.1:8094/index.html?spec=/spec.json%3Fworld%3Dgreenhouse-seventy-coldest-week-t167%26view%3Dheat-coldest-week&full=1
Screenshot (390 wide through CDP): coldest-week-heat-view.png. The view's own note says its temperatures and fan come from the old hoop-house model, not the heat network on the placed pieces.
