package social.surf.api;

import social.surf.api.model.Notification;

import java.util.List;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Notification operations ({@code read:notifications} scope). */
public class NotificationsApi {

    private final SurfClient c;

    NotificationsApi(SurfClient client) {
        this.c = client;
    }

    /** Get notifications (default limit 30). */
    public List<Notification> list() {
        return list(30, null, null);
    }

    /** Get notifications. type: {@code activity} for social activity. */
    public List<Notification> list(int limit, String cursor, String type) {
        return c.getListOf("/notifications", map("limit", limit, "cursor", cursor, "type", type), Notification.class);
    }

    /** Mark notifications as read / reset badge count. */
    public Map<String, Object> markRead() {
        return c.post("/notifications/read");
    }
}
