import { test } from "node:test";
import assert from "node:assert/strict";
import { clock, localDate, dateLabel, groupTasks } from "../.test-build/lib.js";
test("clock rounds remaining seconds up and clamps invalid values", () => {
  assert.equal(clock(59.2), "01:00");
  assert.equal(clock(-1), "00:00");
  assert.equal(clock(Infinity), "00:00");
  assert.equal(clock(3600), "60:00");
});
test("dates use local calendar values, not UTC slicing", () => {
  assert.equal(localDate(new Date(2026, 9, 18, 0, 1)), "2026-10-18");
});
test("today and tomorrow are readable across month boundaries", () => {
  assert.equal(dateLabel("2026-10-31", "2026-10-31"), "Today");
  assert.equal(dateLabel("2026-11-01", "2026-10-31"), "Tomorrow");
});
const tasks = [
  {
    title: "Read 100%",
    planned_date: "2026-10-18",
    priority: 2,
    completed: false,
  },
  { title: "WRITE", planned_date: "2026-10-19", priority: 1, completed: true },
];
test("groups preserve dated tasks and sort newest day first", () => {
  assert.deepEqual(
    groupTasks(tasks, "", "all", "all").map(([day]) => day),
    ["2026-10-19", "2026-10-18"],
  );
});
test("search is case-insensitive and treats SQL wildcard characters literally", () => {
  assert.equal(
    groupTasks(tasks, "write", "all", "all")[0][1][0].title,
    "WRITE",
  );
  assert.equal(groupTasks(tasks, "%", "all", "all").length, 1);
});
test("filters combine without changing the original list", () => {
  assert.equal(groupTasks(tasks, "", "pending", "2").length, 1);
  assert.equal(groupTasks(tasks, "", "completed", "2").length, 0);
  assert.equal(tasks.length, 2);
});
