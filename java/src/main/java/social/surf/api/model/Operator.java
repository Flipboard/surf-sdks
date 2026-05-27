package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * The role an operator (source) plays within a custom feed.
 *
 * <p>Mirrors {@code SurfOperator} from the backend. Unknown values deserialize to
 * {@link #source} rather than failing.
 */
public enum Operator {
    source,
    include,
    filtering_include,
    exclude,
    score;

    @JsonValue
    public String value() {
        return name();
    }

    @JsonCreator
    public static Operator forValue(String value) {
        for (Operator op : values()) {
            if (op.name().equals(value)) {
                return op;
            }
        }
        return source;
    }
}
