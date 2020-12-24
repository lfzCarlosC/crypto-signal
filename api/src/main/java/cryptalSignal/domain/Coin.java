package cryptalSignal.domain;

import java.io.Serializable;

import com.fasterxml.jackson.annotation.JsonProperty;

public class Coin implements Serializable {
    private String name;

    public Coin(@JsonProperty("name") String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }
}
