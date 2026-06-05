package social.surf.api.model;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Feed theme using semantic color names and separated header/color concerns.
 *
 * <pre>{@code
 * FeedTheme theme = FeedTheme.builder()
 *     .headerImage("https://cdn.example.com/logo.png")
 *     .headerImageSize(Map.of("width", 600, "height", 272))
 *     .surface("#EFEADD")
 *     .surfaceHeader("#005F5F")
 *     .build();
 * client.customFeeds.createWithTheme("My Feed", null, theme);
 * }</pre>
 */
public record FeedTheme(
        // Header
        String headerImage,
        String headerImageDark,
        Map<String, Object> headerImageSize,
        Map<String, Object> headerImagePadding,
        String layout,
        Map<String, Object> responsiveCompactImageSize,
        Map<String, Object> responsiveCompactImagePadding,
        // Colors light
        String surface,
        String surfaceHeader,
        String surfaceCard,
        String onSurface,
        String onHeader,
        String accent,
        Map<String, String> extraLight,
        // Colors dark
        String surfaceDark,
        String surfaceHeaderDark,
        String surfaceCardDark,
        String onSurfaceDark,
        String onHeaderDark,
        String accentDark,
        Map<String, String> extraDark
) {
    public static Builder builder() { return new Builder(); }

    /** Convert to the {@code theme} map accepted by the API. */
    public Map<String, Object> toMap() {
        var theme = new LinkedHashMap<String, Object>();

        // Header
        var header = new LinkedHashMap<String, Object>();
        if (headerImage != null) header.put("image", headerImage);
        if (headerImageDark != null) header.put("imageDark", headerImageDark);
        if (headerImageSize != null) header.put("imageSize", headerImageSize);
        if (headerImagePadding != null) header.put("imagePadding", headerImagePadding);
        if (layout != null) header.put("layout", layout);
        if (responsiveCompactImageSize != null || responsiveCompactImagePadding != null) {
            var compact = new LinkedHashMap<String, Object>();
            if (responsiveCompactImageSize != null) compact.put("imageSize", responsiveCompactImageSize);
            if (responsiveCompactImagePadding != null) compact.put("imagePadding", responsiveCompactImagePadding);
            header.put("responsive", Map.of("compact", compact));
        }
        if (!header.isEmpty()) theme.put("header", header);

        // Colors
        var colors = new LinkedHashMap<String, Object>();
        var light = buildPalette(surface, surfaceHeader, surfaceCard, onSurface, onHeader, accent, extraLight);
        if (light != null) colors.put("light", light);
        var dark = buildPalette(surfaceDark, surfaceHeaderDark, surfaceCardDark, onSurfaceDark, onHeaderDark, accentDark, extraDark);
        if (dark != null) colors.put("dark", dark);
        if (!colors.isEmpty()) theme.put("colors", colors);

        return theme;
    }

    private static Map<String, String> buildPalette(
            String surface, String surfaceHeader, String surfaceCard,
            String onSurface, String onHeader, String accent,
            Map<String, String> extras) {
        var p = new LinkedHashMap<String, String>();
        if (surface != null) p.put("surface", surface);
        if (surfaceHeader != null) p.put("surfaceHeader", surfaceHeader);
        if (surfaceCard != null) p.put("surfaceCard", surfaceCard);
        if (onSurface != null) p.put("onSurface", onSurface);
        if (onHeader != null) p.put("onHeader", onHeader);
        if (accent != null) p.put("accent", accent);
        if (extras != null) p.putAll(extras);
        return p.isEmpty() ? null : p;
    }

    public static class Builder {
        private String headerImage, headerImageDark, layout;
        private Map<String, Object> headerImageSize, headerImagePadding;
        private Map<String, Object> responsiveCompactImageSize, responsiveCompactImagePadding;
        private String surface, surfaceHeader, surfaceCard, onSurface, onHeader, accent;
        private String surfaceDark, surfaceHeaderDark, surfaceCardDark, onSurfaceDark, onHeaderDark, accentDark;
        private Map<String, String> extraLight, extraDark;

        public Builder headerImage(String v) { headerImage = v; return this; }
        public Builder headerImageDark(String v) { headerImageDark = v; return this; }
        public Builder headerImageSize(Map<String, Object> v) { headerImageSize = v; return this; }
        /** Convenience: {@code headerImageSize(600, 272)} */
        public Builder headerImageSize(int width, int height) { headerImageSize = Map.of("width", width, "height", height); return this; }
        public Builder headerImagePadding(Map<String, Object> v) { headerImagePadding = v; return this; }
        /** Convenience: {@code headerImagePadding(24, 48)} */
        public Builder headerImagePadding(int top, int bottom) { headerImagePadding = Map.of("top", top, "bottom", bottom); return this; }
        public Builder layout(String v) { layout = v; return this; }
        public Builder responsiveCompactImageSize(Map<String, Object> v) { responsiveCompactImageSize = v; return this; }
        /** Convenience: {@code responsiveCompactImageSize(375, 150)} */
        public Builder responsiveCompactImageSize(int width, int height) { responsiveCompactImageSize = Map.of("width", width, "height", height); return this; }
        public Builder responsiveCompactImagePadding(Map<String, Object> v) { responsiveCompactImagePadding = v; return this; }
        /** Convenience: {@code responsiveCompactImagePadding(12, 24)} */
        public Builder responsiveCompactImagePadding(int top, int bottom) { responsiveCompactImagePadding = Map.of("top", top, "bottom", bottom); return this; }
        public Builder surface(String v) { surface = v; return this; }
        public Builder surfaceHeader(String v) { surfaceHeader = v; return this; }
        public Builder surfaceCard(String v) { surfaceCard = v; return this; }
        public Builder onSurface(String v) { onSurface = v; return this; }
        public Builder onHeader(String v) { onHeader = v; return this; }
        public Builder accent(String v) { accent = v; return this; }
        public Builder extraLight(Map<String, String> v) { extraLight = v; return this; }
        public Builder surfaceDark(String v) { surfaceDark = v; return this; }
        public Builder surfaceHeaderDark(String v) { surfaceHeaderDark = v; return this; }
        public Builder surfaceCardDark(String v) { surfaceCardDark = v; return this; }
        public Builder onSurfaceDark(String v) { onSurfaceDark = v; return this; }
        public Builder onHeaderDark(String v) { onHeaderDark = v; return this; }
        public Builder accentDark(String v) { accentDark = v; return this; }
        public Builder extraDark(Map<String, String> v) { extraDark = v; return this; }

        public FeedTheme build() {
            return new FeedTheme(
                    headerImage, headerImageDark, headerImageSize, headerImagePadding,
                    layout, responsiveCompactImageSize, responsiveCompactImagePadding,
                    surface, surfaceHeader, surfaceCard, onSurface, onHeader, accent, extraLight,
                    surfaceDark, surfaceHeaderDark, surfaceCardDark, onSurfaceDark, onHeaderDark, accentDark, extraDark);
        }
    }
}
