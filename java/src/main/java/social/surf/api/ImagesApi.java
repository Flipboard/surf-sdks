package social.surf.api;

import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Image processing ({@code read:feeds} scope). */
public class ImagesApi {

    private final SurfClient c;

    ImagesApi(SurfClient client) {
        this.c = client;
    }

    /** Get image dimensions and size variant URLs. */
    public Map<String, Object> info(String url) {
        return c.get("/image/info", map("url", url));
    }

    /** Resize an image to the default {@code medium} (500px) size. Returns raw image bytes. */
    public byte[] resize(String url) {
        return resize(url, "medium");
    }

    /**
     * Resize an image. size: small (240px), medium (500px), large (1024px), xlarge (2048px).
     * Returns raw image bytes.
     */
    public byte[] resize(String url, String size) {
        return c.getBytes("/image/resize", map("url", url, "size", size));
    }

    /** Extract a dominant color palette (default k=5). Returns image bytes of the visualization. */
    public byte[] colors(String url) {
        return colors(url, 5);
    }

    /** Extract a dominant color palette. Returns image bytes of the palette visualization. */
    public byte[] colors(String url, int k) {
        return c.getBytes("/image/colors", map("url", url, "k", k));
    }

    /** Check an image for NSFW content. Returns nsfw flag and moderation labels. */
    public Map<String, Object> moderate(String url) {
        return c.get("/image/moderate", map("url", url));
    }
}
