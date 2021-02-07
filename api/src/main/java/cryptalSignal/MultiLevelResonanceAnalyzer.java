package cryptalSignal;

import java.util.AbstractMap;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Properties;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ExitCodeGenerator;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@SpringBootApplication
@EnableScheduling
public class MultiLevelResonanceAnalyzer implements ExitCodeGenerator {

    private static ConfigurableApplicationContext context;
    private static RedisTemplate<String, Object> redisTemplate;
    @Autowired
    private JavaMailSender javaMailSender;

    public static void main(String[] args) {
        context =  SpringApplication.run(MultiLevelResonanceAnalyzer.class, args);
        redisTemplate = context.getBean("redisTemplate", RedisTemplate.class);
    }

    @Scheduled(fixedDelay = 14450000, initialDelay = 1000)
    private void scheduleProcessTask() {
        MultiLevelResonanceAnalyzer multiLevelResonanceAnalyzer = new MultiLevelResonanceAnalyzer();
        List<String> pairs = multiLevelResonanceAnalyzer.getData(redisTemplate);
        Optional<String> pairStr = pairs.stream().reduce((pair1, pair2) -> pair1 + "\n" + pair2);
        if (pairStr.isPresent()) {
            this.send(pairStr.get(), javaMailSender);
        }
    }

    private void send(String pairStr, JavaMailSender javaMailSender) {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setTo("cryptalreceiver@gmail.com");
        message.setFrom("cryptalsender1@gmail.com");
        message.setSubject("级别共振");
        message.setText(pairStr);
        javaMailSender.send(message);
    }

    @Bean
    public JavaMailSender getJavaMailSender() {
        JavaMailSenderImpl mailSender = new JavaMailSenderImpl();
        mailSender.setHost("smtp.gmail.com");
        mailSender.setPort(587);

        mailSender.setUsername("cryptalsender1@gmail.com");
        mailSender.setPassword("868891251q1q1q1q");

        Properties props = mailSender.getJavaMailProperties();
        props.put("mail.transport.protocol", "smtp");
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.starttls.enable", "true");
        props.put("mail.debug", "true");

        return mailSender;
    }

    private void sendEmail(List<String> pairs) {

    }

    // coin:exchange/indicator/level/
    private List<String> getData(RedisTemplate<String, Object> redisTemplate) {
        Set<String> coinWithExchanges = redisTemplate.keys("*");

        return coinWithExchanges.stream().flatMap(coinWithExchange ->
            getIndicatorAndLevel(redisTemplate, coinWithExchange)
            .filter(indicatorEntry -> indicatorEntry.getValue().size() > 1)
            .map(indicatorEntry -> coinWithExchange + ":" + indicatorEntry.getKey() + ":" + indicatorEntry.getValue())
        ).collect(Collectors.toList());
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
