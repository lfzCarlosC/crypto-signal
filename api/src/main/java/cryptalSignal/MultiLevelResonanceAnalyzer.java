package cryptalSignal;

import java.util.AbstractMap;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

import org.springframework.boot.ExitCodeGenerator;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.data.redis.core.RedisTemplate;

@SpringBootApplication
public class MultiLevelResonanceAnalyzer implements ExitCodeGenerator {

    public static void main(String[] args) {
        ConfigurableApplicationContext context =  SpringApplication.run(MultiLevelResonanceAnalyzer.class, args);
        RedisTemplate<String, Object> redisTemplate = context.getBean("redisTemplate", RedisTemplate.class);
        MultiLevelResonanceAnalyzer multiLevelResonanceAnalyzer = new MultiLevelResonanceAnalyzer();
        System.out.println("==========================");
        multiLevelResonanceAnalyzer.getData(redisTemplate);
        System.out.println("==========================");
        System.exit(SpringApplication.exit(context));
    }

    // coin:exchange/indicator/level/
    private void getData(RedisTemplate<String, Object> redisTemplate) {
        Set<String> coinWithExchanges = redisTemplate.keys("*");

        coinWithExchanges.forEach(coinWithExchange -> {
            getIndicatorAndLevel(redisTemplate, coinWithExchange)
            .filter(indicatorEntry -> indicatorEntry.getValue().size() > 1)
            .map(indicatorEntry -> coinWithExchange + ":" + indicatorEntry.getKey() + ":" + indicatorEntry.getValue())
            .forEach(x -> System.out.println(x));
        });
    }

    private Stream<AbstractMap.SimpleEntry<String, List<String>>> getIndicatorAndLevel(RedisTemplate<String, Object> redisTemplate, String coinExchange) {
        Map<Object, Object> indicatorAndLevels = redisTemplate.opsForHash().entries(coinExchange);
        return indicatorAndLevels.entrySet().stream().map(indicatorAndLevel ->
                new AbstractMap.SimpleEntry<>((String) indicatorAndLevel.getKey(),
                       Arrays.asList(((String)indicatorAndLevel.getValue()).split("\\|")))
        );
    }


    @Override
    public int getExitCode() {
        return 0;
    }
}
