// On-device local reminder scheduling for exam / assignment deadlines.
// Purely local (no push server, no Firebase, no keys). Web is a no-op.
import { Platform, Linking } from "react-native";
import * as Notifications from "expo-notifications";
import { storage } from "@/src/utils/storage";

export const DEADLINE_CHANNEL_ID = "deadlines";
const REMINDER_HOUR = 8; // 08:00 local

// Foreground presentation behaviour.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export type PermissionState = "granted" | "denied" | "blocked" | "unsupported";

export async function ensureReminderPermission(): Promise<PermissionState> {
  if (Platform.OS === "web") return "unsupported";

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(DEADLINE_CHANNEL_ID, {
      name: "Deadline reminders",
      description: "Reminders for upcoming exams and tasks",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      sound: "default",
    });
  }

  const current = await Notifications.getPermissionsAsync();
  if (current.status === "granted") return "granted";
  if (current.status === "denied" && !current.canAskAgain) return "blocked";

  const requested = await Notifications.requestPermissionsAsync();
  if (requested.status === "granted") return "granted";
  if (!requested.canAskAgain) return "blocked";
  return "denied";
}

export function openNotificationSettings() {
  Linking.openSettings().catch(() => {});
}

// Parse a "YYYY-MM-DD" string into a LOCAL Date at the given hour (avoids UTC shift).
function localDateAt(dateStr: string, hour: number): Date | null {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(dateStr);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), hour, 0, 0, 0);
}

async function scheduleOne(title: string, body: string, when: Date): Promise<string | null> {
  if (when.getTime() <= Date.now()) return null; // never schedule in the past
  return Notifications.scheduleNotificationAsync({
    content: { title, body, sound: "default", data: { type: "deadline" } },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DATE,
      date: when,
      ...(Platform.OS === "android" ? { channelId: DEADLINE_CHANNEL_ID } : {}),
    },
  });
}

// Schedule 3-days-before, 1-day-before, and morning-of reminders for a dated milestone.
export async function scheduleDeadlineReminders(opts: {
  id: string;
  label: string; // e.g. "Biology exam"
  dateStr: string; // "YYYY-MM-DD"
}): Promise<number> {
  if (Platform.OS === "web") return 0;
  const due = localDateAt(opts.dateStr, REMINDER_HOUR);
  if (!due) return 0;

  const three = localDateAt(opts.dateStr, REMINDER_HOUR);
  const one = localDateAt(opts.dateStr, REMINDER_HOUR);
  if (three) three.setDate(three.getDate() - 3);
  if (one) one.setDate(one.getDate() - 1);

  const plan: [string, string, Date | null][] = [
    ["3 days to go", `${opts.label} is in 3 days — start reviewing.`, three],
    ["Tomorrow", `${opts.label} is tomorrow. Time for a final review.`, one],
    ["Today", `${opts.label} is today. You've got this.`, due],
  ];

  const ids: string[] = [];
  for (const [title, body, when] of plan) {
    if (!when) continue;
    const nid = await scheduleOne(title, body, when);
    if (nid) ids.push(nid);
  }
  await storage.setItem(`reminders:${opts.id}`, ids.join(","));
  return ids.length;
}

export async function cancelDeadlineReminders(id: string): Promise<void> {
  if (Platform.OS === "web") return;
  const raw = (await storage.getItem<string>(`reminders:${id}`, "")) || "";
  const ids = raw.split(",").filter(Boolean);
  await Promise.all(ids.map((nid) => Notifications.cancelScheduledNotificationAsync(nid)));
  await storage.removeItem(`reminders:${id}`);
}
