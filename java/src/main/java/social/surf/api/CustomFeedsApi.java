package social.surf.api;

import social.surf.api.model.CustomFeed;
import social.surf.api.model.FeedTheme;
import social.surf.api.model.NewFeedOperator;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/**
 * Custom feed operations ({@code write:feeds} scope).
 *
 * <p>Uses the public {@code /custom/*} paths (rewritten to
 * {@code /builder/surf/custom/*} internally).
 */
public class CustomFeedsApi {

    private final SurfClient c;

    CustomFeedsApi(SurfClient client) {
        this.c = client;
    }

    /** List custom feeds owned by the authenticated user. */
    public List<CustomFeed> list() {
        return c.getListOf("/custom", null, CustomFeed.class);
    }

    /** Get a custom feed by ID. */
    public CustomFeed get(String feedId) {
        return c.getAs("/custom/" + feedId, null, CustomFeed.class);
    }

    /** Create a new custom feed. */
    public CustomFeed create(String title) {
        return create(title, null, null);
    }

    /** Create a new custom feed with a description. */
    public CustomFeed create(String title, String description) {
        return create(title, description, null);
    }

    /** Create a new custom feed with a description and operators (sources). */
    public CustomFeed create(String title, String description, List<Map<String, Object>> operators) {
        return c.postAs("/custom", map("title", title, "description", description, "operators", operators), CustomFeed.class);
    }

    /**
     * Create a new custom feed with typed operators.
     *
     * <p>Convenience overload that takes a list of {@link NewFeedOperator} records
     * (the writable subset of {@code FeedOperator} — no server-assigned fields):
     *
     * <pre>{@code
     * client.customFeeds.createWithOperators("AI News", "Latest AI", List.of(
     *     NewFeedOperator.source("surf/topic/artificial-intelligence"),
     *     NewFeedOperator.source("surf/hashtag/machinelearning")
     * ));
     * }</pre>
     *
     * @param title       feed title (required)
     * @param description feed description, or null
     * @param operators   the operators (sources) that define the feed
     */
    public CustomFeed createWithOperators(String title, String description, List<NewFeedOperator> operators) {
        return c.postAs("/custom", map("title", title, "description", description, "operators", operators), CustomFeed.class);
    }

    /**
     * Create a new custom feed with a visual theme.
     *
     * <pre>{@code
     * FeedTheme theme = FeedTheme.builder()
     *     .headerImage("https://cdn.example.com/logo.png")
     *     .headerImageSize(600, 272)
     *     .surface("#EFEADD")
     *     .surfaceHeader("#005F5F")
     *     .build();
     * client.customFeeds.createWithTheme("My Feed", "Description", theme);
     * }</pre>
     */
    public CustomFeed createWithTheme(String title, String description, FeedTheme theme) {
        var body = new LinkedHashMap<String, Object>();
        body.put("title", title);
        if (description != null) body.put("description", description);
        if (theme != null) body.put("theme", theme.toMap());
        return c.postAs("/custom", body, CustomFeed.class);
    }

    /** Update a custom feed. */
    public CustomFeed update(String feedId, Map<String, Object> fields) {
        return c.putAs("/custom/" + feedId, fields, CustomFeed.class);
    }

    /**
     * Update a custom feed with a visual theme.
     *
     * <p>This is a full-replace operation — omitted fields are cleared.
     * Always re-send the complete state you want to preserve.
     */
    public CustomFeed update(String feedId, Map<String, Object> fields, FeedTheme theme) {
        var body = new LinkedHashMap<>(fields);
        if (theme != null) body.put("theme", theme.toMap());
        return c.putAs("/custom/" + feedId, body, CustomFeed.class);
    }

    /** Delete a custom feed. */
    public Map<String, Object> delete(String feedId) {
        return c.delete("/custom/" + feedId);
    }

    /** Clone an existing custom feed. */
    public CustomFeed clone(String feedId) {
        return c.postAs("/custom/" + feedId + "/clone", null, CustomFeed.class);
    }

    /** Publish a custom feed (makes it publicly discoverable). */
    public CustomFeed publish(String feedId) {
        return c.postAs("/custom/" + feedId + "/publish", null, CustomFeed.class);
    }

    /** Unpublish a custom feed. */
    public CustomFeed unpublish(String feedId) {
        return c.postAs("/custom/" + feedId + "/unpublish", null, CustomFeed.class);
    }

    /** Add an operator (source) to a custom feed. Returns the updated feed. */
    public CustomFeed addOperator(String feedId, Map<String, Object> operator) {
        return c.postAs("/custom/" + feedId + "/operators", List.of(operator), CustomFeed.class);
    }

    /** Add multiple operators to a custom feed. Returns the updated feed. */
    public CustomFeed addOperators(String feedId, List<?> operators) {
        return c.postAs("/custom/" + feedId + "/operators", operators, CustomFeed.class);
    }

    /** Add a typed operator to a custom feed. Returns the updated feed. */
    public CustomFeed addOperator(String feedId, NewFeedOperator operator) {
        return c.postAs("/custom/" + feedId + "/operators", List.of(operator), CustomFeed.class);
    }

    /** Update an operator in a custom feed. Returns the updated feed. */
    public CustomFeed updateOperator(String feedId, String operatorId, Map<String, Object> operator) {
        return c.putAs("/custom/" + feedId + "/operators/" + operatorId, operator, CustomFeed.class);
    }

    /** Remove an operator from a custom feed. Returns the updated feed. */
    public CustomFeed removeOperator(String feedId, String operatorId) {
        return c.deleteAs("/custom/" + feedId + "/operators/" + operatorId, CustomFeed.class);
    }
}
