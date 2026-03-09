package com.s14p21a503.matcher.journal;

import java.io.*;

/**
 * 저널 페이로드 직렬화 유틸리티.
 */
public class JournalSerializer {
    
    public static byte[] serialize(Object obj) throws IOException {
        if (obj == null) return null;
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutputStream oos = new ObjectOutputStream(bos)) {
            oos.writeObject(obj);
            return bos.toByteArray();
        }
    }

    public static Object deserialize(byte[] data) throws IOException, ClassNotFoundException {
        if (data == null) return null;
        try (ByteArrayInputStream bis = new ByteArrayInputStream(data);
             ObjectInputStream ois = new ObjectInputStream(bis)) {
            return ois.readObject();
        }
    }
}
