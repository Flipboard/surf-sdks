package social.surf.api;

import social.surf.api.model.MediaUploadResponse;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/** Media operations. */
public class MediaApi {

    private final SurfClient c;

    MediaApi(SurfClient client) {
        this.c = client;
    }

    /** Upload a media file (image) with the default {@code image/jpeg} content type. */
    public MediaUploadResponse upload(String filePath) {
        return upload(Paths.get(filePath), "image/jpeg");
    }

    /** Upload a media file (image). */
    public MediaUploadResponse upload(String filePath, String contentType) {
        return upload(Paths.get(filePath), contentType);
    }

    /** Upload a media file (image) from a {@link Path}. */
    public MediaUploadResponse upload(Path file, String contentType) {
        byte[] bytes;
        try {
            bytes = Files.readAllBytes(file);
        } catch (IOException e) {
            throw new SurfAPIError("Failed to read file " + file + ": " + e.getMessage());
        }
        String filename = file.getFileName() == null ? "upload" : file.getFileName().toString();
        return c.uploadMultipart("/media/upload", bytes, filename, contentType, MediaUploadResponse.class);
    }
}
