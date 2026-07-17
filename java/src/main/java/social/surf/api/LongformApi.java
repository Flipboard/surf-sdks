package social.surf.api;

import social.surf.api.model.Document;
import social.surf.api.model.Publication;
import social.surf.api.model.PublicationDocumentEntry;

import java.util.List;

import static social.surf.api.SurfClient.map;

/**
 * Longform documents &amp; publications — standard.site / Leaflet.
 *
 * <p>Documents and publications are addressed by AT-URI (e.g.
 * {@code at://did:plc:x/site.standard.document/3k2a}). Pass the raw AT-URI —
 * the SDK percent-encodes it into the path automatically. Read endpoints require
 * the {@code read:feeds} scope; {@link #searchPublications(String)} requires
 * {@code read:search}.
 *
 * <p>Post maps returned elsewhere in the SDK (e.g. {@link FeedsApi#getPosts(String)})
 * may include an optional {@code document} summary object
 * ({@code title, description, cover_image_url, tags, publication_uri}) when the
 * post links to a longform document.
 */
public class LongformApi {

    private final SurfClient c;

    LongformApi(SurfClient client) {
        this.c = client;
    }

    /** Get a longform document by AT-URI in the default {@code html} format. */
    public Document getDocument(String uri) {
        return getDocument(uri, null);
    }

    /**
     * Get a longform document by AT-URI.
     *
     * @param uri    document AT-URI (raw; encoded internally)
     * @param format {@code "html"} (default) populates {@link Document#contentHtml()};
     *               {@code "blocks"} populates the raw block {@link Document#pages()}.
     *               Null omits the parameter (server default {@code html}).
     */
    public Document getDocument(String uri, String format) {
        return c.getAs("/documents/" + enc(uri), map("format", format), Document.class);
    }

    /** Get a publication by AT-URI (raw; encoded internally). */
    public Publication getPublication(String uri) {
        return c.getAs("/publications/" + enc(uri), null, Publication.class);
    }

    /** List a publication's documents, newest first (default count 20, offset 0). */
    public List<PublicationDocumentEntry> listDocuments(String uri) {
        return listDocuments(uri, null, 20, 0);
    }

    /** List a publication's documents with a page size. */
    public List<PublicationDocumentEntry> listDocuments(String uri, int count) {
        return listDocuments(uri, null, count, 0);
    }

    /**
     * List a publication's documents with full options.
     *
     * @param uri   publication AT-URI (raw; encoded internally)
     * @param tags  optional tags to filter by (sent as a repeated {@code tags} query
     *              param); null or empty to skip filtering
     * @param count page size (default 20, max 100)
     * @param from  result offset (default 0)
     */
    public List<PublicationDocumentEntry> listDocuments(String uri, List<String> tags, int count, int from) {
        return c.getListOf("/publications/" + enc(uri) + "/documents",
                map("tags", tags, "count", count, "from", from),
                PublicationDocumentEntry.class);
    }

    /** Search publications by name/description ({@code read:search} scope, default count 20). */
    public List<Publication> searchPublications(String q) {
        return searchPublications(q, 20, 0);
    }

    /** Search publications with a page size. */
    public List<Publication> searchPublications(String q, int count) {
        return searchPublications(q, count, 0);
    }

    /**
     * Search publications with full options.
     *
     * @param q     search query (required)
     * @param count page size (default 20, max 100)
     * @param from  result offset (default 0)
     */
    public List<Publication> searchPublications(String q, int count, int from) {
        return c.getListOf("/search/publications",
                map("q", q, "count", count, "from", from),
                Publication.class);
    }

    /**
     * Percent-encode an AT-URI for use as a single URL path segment: {@code :} and
     * {@code /} must be escaped ({@code at%3A%2F%2F...}) or the gateway splits the
     * URI into extra path segments and misses the route.
     */
    private static String enc(String uri) {
        return SurfClient.encodePathSegment(uri);
    }
}
