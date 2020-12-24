package cryptalSignal.repository;

import java.util.List;

import cryptalSignal.domain.Coin;

public interface SignalDataRepository {
    public List<Coin> getCoins(String key);
}
