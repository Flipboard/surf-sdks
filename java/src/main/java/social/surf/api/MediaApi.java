package social.surf.api;

import social.surf.api.model.GenerateImageJob;
import social.surf.api.model.MediaUploadResponse;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.Map;

import static social.surf.api.SurfClient.map;

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

    /**
     * Start AI generation of a feed cover image (Stable Diffusion XL). Requires the
     * {@code use:ai} scope. Async submit/poll: returns immediately with a
     * {@link GenerateImageJob} ({@code key}, {@code url}, {@code status="pending"}) —
     * generation runs server-side and can take a couple of minutes. Poll
     * {@link #getGenerateImageStatus} with the {@code key} until {@code done}, then use
     * {@code url}; or call {@link #generateImageAndWait} to do both.
     */
    public GenerateImageJob generateImage(String prompt) {
        return generateImage(prompt, false);
    }

    /** Start generation, optionally skipping the SDXL refiner ({@code skipRefiner=true} is faster, lower quality). */
    public GenerateImageJob generateImage(String prompt, boolean skipRefiner) {
        return c.postAs("/media/generate-image", map("prompt", prompt, "skipRefiner", skipRefiner),
                GenerateImageJob.class);
    }

    /** Poll a generation job. Returns a map with {@code status}: pending / done / failed / not_found. */
    public Map<String, Object> getGenerateImageStatus(String key) {
        return c.get("/media/generate-image/status", map("key", key));
    }

    /**
     * Submit a generation job and block until it completes, returning the image URL.
     * Polls every 4s up to 10 minutes.
     *
     * @throws SurfAPIError if generation fails or times out (or the wait is interrupted)
     */
    public String generateImageAndWait(String prompt, boolean skipRefiner) {
        GenerateImageJob job = generateImage(prompt, skipRefiner);
        long pollMs = Duration.ofSeconds(4).toMillis();
        long deadline = System.currentTimeMillis() + Duration.ofMinutes(10).toMillis();
        while (System.currentTimeMillis() < deadline) {
            try {
                Thread.sleep(pollMs);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new SurfAPIError("Interrupted while waiting for image generation");
            }
            Object status = getGenerateImageStatus(job.key()).get("status");
            if ("done".equals(status)) {
                return job.url();
            }
            if ("failed".equals(status) || "not_found".equals(status)) {
                throw new SurfAPIError("Image generation " + status);
            }
        }
        throw new SurfAPIError("Image generation timed out");
    }
}
