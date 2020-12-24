package cryptalSignal.repository.impl;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Repository;

import cryptalSignal.domain.Coin;
import cryptalSignal.repository.SignalDataRepository;

@Repository
public class SignalDataRepositoryImpl implements SignalDataRepository {

    @Autowired
    RedisTemplate<String, Object> redisTemplate;

    public List<Coin> getCoins(String key) {
        return (key == null) ? null : (List<Coin>) redisTemplate.opsForValue().get(key);
    }
}
